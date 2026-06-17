"""OpenAI-compatible structured LLM call with model-chain fallback + retries.

Vendored from the deployed agent A (`analyze.py`). The LLM only ever returns JSON
validated against a Pydantic schema; callers never parse free text.
"""
import json
import random
import time
from pydantic import BaseModel, ValidationError
from openai import RateLimitError, APITimeoutError, APIConnectionError

from app import governor

T_MODEL = type[BaseModel]

# Transient API failures worth waiting out (rate limits, timeouts, blips).
_TRANSIENT = (RateLimitError, APITimeoutError, APIConnectionError)
# Round-robin wait schedule (seconds). Each round tries EVERY model in order,
# then sleeps this long before the next round. Round 0 waits 0s so a fallback
# model on a different provider pool is tried immediately on a 429.
_ROUND_WAITS = (0, 2, 4, 8, 12, 18)


class StageError(Exception):
    """Raised when an LLM stage cannot produce valid structured output."""


class RateLimitedError(StageError):
    """Raised when every configured model is rate-limited / unavailable."""


def _normalize_models(model) -> list[str]:
    """Accept a single model name, a comma-separated string, or a list → list[str]."""
    if isinstance(model, str):
        return [m.strip() for m in model.split(",") if m.strip()]
    return [m for m in model if m]


def _extra_for(model: str, thinking: bool) -> dict:
    """Per-model request extras. Qwen3 models are reasoning models with a 'thinking' phase that
    consumes the token budget before emitting content. Enable it on high-reasoning stages (better
    quality); disable it on mechanical stages so the budget goes to the JSON reply instead of
    leaving it empty. Non-qwen models take no extra.
    """
    if "qwen" in model.lower():
        return {"extra_body": {"chat_template_kwargs": {"enable_thinking": thinking}}}
    return {}


def _create_resilient(client, models, *, thinking: bool = False, **kwargs):
    """Call chat.completions.create across a chain of models with rate governing + round-robin retries.

    The chain start is rotated per call to spread load across model buckets, and each attempt is
    paced by the governor. On a transient error the next model is tried immediately; waits grow
    between rounds. Non-transient errors propagate at once so we never waste quota.
    """
    models = governor.next_order(models)
    primary = models[0]
    last_exc = None
    for wait in _ROUND_WAITS:
        if wait:
            time.sleep(wait + random.uniform(0, 1))  # jitter avoids thundering herd
        for model in models:
            try:
                governor.acquire(model)  # block until this model's bucket has room
                resp = client.chat.completions.create(
                    model=model, **_extra_for(model, thinking), **kwargs)
                if model != primary:
                    print(f"[fallback] {primary} rate-limited; served by {model}", flush=True)
                return resp
            except _TRANSIENT as exc:
                last_exc = exc
    raise RateLimitedError(f"all models rate-limited ({', '.join(models)}); last: {last_exc}")


def call_structured(client, model, system: str, user: str,
                    schema: T_MODEL, *, temperature: float = 0.0, _retries: int = 1,
                    thinking: bool = False):
    """Call an OpenAI-compatible chat model, parse + validate JSON into `schema`.

    `model` may be a single name, a comma-separated string, or a list; the chain is
    tried in order on rate limits. Retries once more with the validation/parse error
    appended if the JSON is malformed. `thinking` toggles the qwen reasoning phase.
    """
    models = _normalize_models(model)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_error = ""
    for attempt in range(_retries + 1):
        if attempt > 0:
            messages.append({
                "role": "user",
                "content": f"Your previous reply was invalid: {last_error}. "
                           f"Reply ONLY with JSON matching the schema.",
            })
        resp = _create_resilient(
            client,
            models,
            thinking=thinking,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        content = resp.choices[0].message.content or ""
        try:
            return schema.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:500]
    raise StageError(f"invalid structured output for {schema.__name__}: {last_error}")
