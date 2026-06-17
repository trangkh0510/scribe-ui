"""Pre-LLM required-field gate (spec §5.2, Step-4 render gate).

Runs BEFORE any LLM call so we never spend tokens on an under-specified request.
Returns precise, field-named reasons the render is blocked.
"""
from dataclasses import dataclass, field
from typing import List

from app.models import InvocationRequest, Transcript

# Brain prompts' own "transcript_too_short" thresholds (words).
MIN_WORDS = {"ux": 500, "cs": 300, "meeting": 500}


@dataclass
class GateResult:
    ok: bool
    missing: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _word_count(transcripts: List[Transcript]) -> int:
    return sum(len(t.text.split()) for t in transcripts)


def gate(req: InvocationRequest, transcripts: List[Transcript]) -> GateResult:
    missing: List[str] = []
    errors: List[str] = []

    # 1. Required-field presence.
    if not req.objectives or not req.objectives.strip():
        missing.append("objectives")
    if not req.files:
        missing.append("files")

    # 2. Single-file only (Route A).
    n = len(req.files)
    if n != 1:
        errors.append(f"single mode expects exactly 1 file (got {n})")

    # 3. Per-type minimum length (only meaningful once we have extractable text).
    if transcripts:
        threshold = MIN_WORDS.get(req.type, 0)
        words = _word_count(transcripts)
        if words < threshold:
            errors.append(
                f"transcript_too_short: {words} words < {threshold} required for type '{req.type}'"
            )

    ok = not missing and not errors
    return GateResult(ok=ok, missing=missing, errors=errors)
