"""Stage: Prepare transcript — v1 PLACEHOLDER SEAM.

v1 is a passthrough. The future Prepare skill plugs in here and will:
  - AUDIO SEAM: transcribe audio (Whisper) + diarize (pyannote) → text, and
  - clean: filler strip / dedupe rolling captions / assign speaker roles
per `brief_ai_agent_clean_transcript.md`. Keep this signature stable so that
work is drop-in.
"""
from typing import List, Tuple

from app.models import Transcript


def prepare(transcripts: List[Transcript], *, type: str) -> Tuple[List[Transcript], List[str]]:
    notes = ["prepare: passthrough (v1)"]
    # AUDIO SEAM: future audio→text+clean step transforms `transcripts` here.
    return transcripts, notes
