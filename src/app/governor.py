"""Process-local rate governor: paces LLM requests to stay under per-(account, model) limits.

The MaaS quota is enforced per (account, model), so each model name is its own bucket. This module
blocks a caller just long enough *before* a request that the model's request rate stays under its
configured limit — turning would-be 429s into short, predictable pre-call waits. It also rotates
the starting model of a fallback chain so consecutive calls spread across buckets instead of
hammering the first one until it 429s, then spilling over.

Limits are read once from the environment:
  LLM_RPM_DEFAULT  int   requests-per-minute for any model without an explicit limit (default 6)
  LLM_RPM_LIMITS   JSON  map of model name -> requests-per-minute, e.g.
                         {"qwen/qwen3-5-27b": 6, "qwen/qwen3.6-27b": 6}

State is per-process (a module singleton). With the runtime pinned to a single replica this is the
whole picture; across replicas each process paces independently (see deploy notes / Pass 2).
"""
import itertools
import json
import os
import threading
import time
from collections import deque

_WINDOW_SECONDS = 60.0
_DEFAULT_RPM = 6


def _load_limits() -> tuple[int, dict[str, int]]:
    """Read LLM_RPM_DEFAULT and LLM_RPM_LIMITS from the environment (best-effort, never raises)."""
    default = _DEFAULT_RPM
    raw_default = os.environ.get("LLM_RPM_DEFAULT", "").strip()
    if raw_default:
        try:
            default = max(1, int(raw_default))
        except ValueError:
            pass
    limits: dict[str, int] = {}
    raw_map = os.environ.get("LLM_RPM_LIMITS", "").strip()
    if raw_map:
        try:
            limits = {str(k): max(1, int(v)) for k, v in json.loads(raw_map).items()}
        except (ValueError, TypeError, AttributeError):
            limits = {}
    return default, limits


class _Governor:
    """Per-model sliding-window requests-per-minute limiter (thread-safe)."""

    def __init__(self) -> None:
        self._default, self._limits = _load_limits()
        self._lock = threading.Lock()
        self._calls: dict[str, deque] = {}  # model -> recent request timestamps (monotonic)

    def _limit_for(self, model: str) -> int:
        return self._limits.get(model, self._default)

    def acquire(self, model: str) -> None:
        """Block until issuing one request for `model` keeps it under its RPM limit, then record it."""
        limit = self._limit_for(model)
        while True:
            with self._lock:
                now = time.monotonic()
                window = self._calls.setdefault(model, deque())
                while window and now - window[0] >= _WINDOW_SECONDS:
                    window.popleft()
                if len(window) < limit:
                    window.append(now)
                    return
                wait = _WINDOW_SECONDS - (now - window[0])
            time.sleep(max(wait, 0.0) + 0.01)


_GOVERNOR = _Governor()


def acquire(model: str) -> None:
    """Block until a request slot is free for `model` (module-level entry point)."""
    _GOVERNOR.acquire(model)


_rotation = itertools.count()
_rotation_lock = threading.Lock()


def next_order(models) -> list:
    """Rotate the model chain so consecutive calls start on different buckets.

    Preserves chain order — just shifts the starting index by a per-call counter — so the chain's
    fallback preference is kept while load spreads across the leading models. The caller treats the
    returned models[0] as the 'primary' it attempts first.
    """
    models = list(models)
    if len(models) <= 1:
        return models
    with _rotation_lock:
        i = next(_rotation)
    start = i % len(models)
    return models[start:] + models[:start]
