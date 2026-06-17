"""Orchestrator: ingest → gate → prepare → analyze (Route A, single-file) → render → response.

Stateless. Returns the API contract dict (status/html/report_json/meta/error).
The LLM only ever emits schema-validated JSON; Python owns all HTML.
"""
import os
from datetime import datetime, timezone
from typing import List

from pydantic import ValidationError

from app.models import InvocationRequest, Transcript
from app.ingest import ingest
from app.gate import gate
from app.prepare import prepare
from app.analyze_single import analyze_single
from app.render.render import render_report

AUDIO_EXT = {".mp3", ".mp4", ".wav", ".m4a", ".webm"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _meta(req=None, transcripts=None, warnings=None, notes=None, model="", **extra) -> dict:
    m = {
        "type": getattr(req, "type", None),
        "mode": getattr(req, "mode", None),
        "file_count": len(req.files) if req else 0,
        "language": getattr(getattr(req, "options", None), "language", "auto"),
        "warnings": warnings or [],
        "prepare_notes": notes or [],
        "model": model,
        "generated_at": _now(),
    }
    m.update(extra)
    return m


def _error(msg: str, **meta_kw) -> dict:
    return {"status": "error", "html": "", "report_json": {},
            "error": msg, "meta": _meta(**meta_kw)}


def run_pipeline(payload: dict, client, model: str) -> dict:
    """Route A only — single-file analysis. `model` runs the analyzer call."""
    # 1. Parse the request contract.
    try:
        req = InvocationRequest.model_validate(payload)
    except ValidationError as exc:
        return _error(f"invalid request: {exc}")

    warnings: List[str] = []

    # 2. Audio is reserved for the future Prepare skill — not supported in v1.
    text_files = []
    for f in req.files:
        ext = os.path.splitext(f.name)[1].lower()
        if ext in AUDIO_EXT:
            warnings.append(f"audio not supported yet (Prepare skill pending): {f.name or '<unnamed>'}")
        else:
            text_files.append(f)

    # 3. Ingest text files → transcripts.
    ing = ingest({"files": [f.model_dump() for f in text_files]})
    warnings += ing.warnings
    transcripts: List[Transcript] = ing.transcripts

    # 4. Gate (required fields, single-file count, per-type length) — before any LLM call.
    g = gate(req, transcripts)
    if not g.ok:
        reason = "; ".join([f"missing: {m}" for m in g.missing] + g.errors)
        return _error(reason, req=req, warnings=warnings, model=model)

    if not transcripts:
        return _error("no extractable text from the uploaded file(s)",
                      req=req, warnings=warnings, model=model)

    # 5. Prepare (passthrough seam).
    transcripts, notes = prepare(transcripts, type=req.type)

    # 6. Analyze (Route A — single file) + render.
    data = analyze_single(
        client, model, type=req.type,
        transcript_text=transcripts[0].text,
        objectives=req.objectives,
        context=req.options.study_title or "",
        language=req.options.language,
    )
    html = render_report(data)
    return {"status": "success", "html": html, "report_json": data, "error": "",
            "meta": _meta(req=req, transcripts=transcripts, warnings=warnings,
                          notes=notes, model=model)}
