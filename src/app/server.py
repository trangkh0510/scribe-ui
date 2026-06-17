"""GreenNode AgentBase SDK server — merged Clean + Analyze agent.

Routes:
  GET  /            wizard UI (Step 1 clean → Step 2 analyze, same origin)
  POST /api/chat    LLM proxy for the in-browser cleaner (injects LLM_API_KEY server-side)
  POST /invocations analyzer handler (Route A — single file → HTML report)
  ping              health

Run locally: `python -m app.server` (serves on :8080).
"""
import json
import os
import random
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI
from starlette.routing import Route
from starlette.responses import HTMLResponse, Response
from starlette.concurrency import run_in_threadpool
from greennode_agentbase import GreenNodeAgentBaseApp, RequestContext, PingStatus

from app import governor
from app.pipeline import run_pipeline

# Server-side backoff schedule (seconds) for the clean proxy on upstream 429.
# Shares the per-model governor with /invocations so the two steps don't self-inflict
# rate limits; waits grow toward the MaaS per-minute window before giving up.
_PROXY_WAITS = (0, 5, 12, 25)

load_dotenv()
app = GreenNodeAgentBaseApp()

_UI_PATH = os.path.join(os.path.dirname(__file__), "templates", "ui.html")


def serve_ui(request):
    """GET / — the wizard (same origin as /invocations and /api/chat, so no CORS)."""
    with open(_UI_PATH, encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


def _chat_upstream() -> str:
    base = (os.environ.get("LLM_BASE_URL") or "").rstrip("/")
    return f"{base}/chat/completions"


def _forward_chat(body: bytes) -> tuple[int, bytes, str]:
    """Blocking POST to the MaaS chat endpoint with the server-side key. Run in a threadpool.

    Paced by the shared per-model governor (same instance /invocations uses) so the clean and
    analyze steps don't trip each other's MaaS limit, with a growing backoff retry on upstream 429.
    """
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        return 500, b'{"error":{"message":"server missing LLM_API_KEY"}}', "application/json"

    # Force the server-configured model so the cleaner never hardcodes one (and never targets a
    # model whose MaaS bucket is exhausted while the configured one has room). Primary = first
    # entry of LLM_MODEL; falls back to whatever the client sent.
    primary = (os.environ.get("LLM_MODEL", "").split(",")[0] or "").strip()
    try:
        data = json.loads(body or b"{}") or {}
    except (ValueError, TypeError):
        data = {}
    if primary:
        data["model"] = primary
        body = json.dumps(data).encode("utf-8")
    model = data.get("model", "")

    last = (502, b'{"error":{"message":"proxy error"}}', "application/json")
    for i, wait in enumerate(_PROXY_WAITS):
        if wait:
            time.sleep(wait + random.uniform(0, 1))  # jitter avoids thundering herd
        if model:
            governor.acquire(model)  # block until this model's rate bucket has room
        req = urllib.request.Request(
            _chat_upstream(),
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return 200, resp.read(), "application/json"
        except urllib.error.HTTPError as exc:
            data = exc.read() or str(exc).encode()
            if exc.code == 429 and i < len(_PROXY_WAITS) - 1:
                last = (429, data, "application/json")
                continue  # retry after backoff
            return exc.code, data, "application/json"
        except Exception as exc:  # noqa: BLE001 — surface as a JSON error to the browser
            return 502, f'{{"error":{{"message":"proxy error: {exc}"}}}}'.encode(), "application/json"
    return last


async def proxy_chat(request):
    """POST /api/chat — Step 1 cleaner proxy. Forwards the browser's chat-completions
    request to the MaaS endpoint with the API key attached server-side (key never reaches
    the client). The cleaner toggles/chunking/prompt all live in the browser; this is a
    thin, stateless passthrough."""
    body = await request.body()
    status, data, ctype = await run_in_threadpool(_forward_chat, body)
    return Response(content=data, status_code=status, media_type=ctype)


app.router.routes.append(Route("/", serve_ui, methods=["GET"]))
app.router.routes.append(Route("/api/chat", proxy_chat, methods=["POST"]))


def _get_client():
    # Generous per-call timeout — GreenNode 27B serving is ~55s/call (qwen reasoning slower still).
    # The rate governor + _create_resilient (app/llm.py) own the retry/backoff/fallback policy,
    # so keep the SDK's hidden retries low (1) to avoid stacking against the governor's pacing.
    client = OpenAI(
        api_key=os.environ.get("LLM_API_KEY", "not-needed"),
        base_url=os.environ.get("LLM_BASE_URL"),
        max_retries=1,
        timeout=180.0,
    )
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    return client, model


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    try:
        client, model = _get_client()
        return run_pipeline(payload, client, model)
    except Exception as exc:  # never surface an unhandled 500
        return {"status": "error", "html": "", "report_json": {},
                "error": f"unexpected failure: {exc}",
                "meta": {"generated_at": datetime.now(timezone.utc).isoformat()}}


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
