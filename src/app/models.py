"""App-level request + transcript contracts.

These are the orchestrator's I/O models. The per-type analyzer output schemas live
in `app/brain_schema.py`. This agent runs Route A only (single-file analysis).
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class FileItem(BaseModel):
    name: str = ""
    content_base64: str = ""
    participant: Optional[str] = None


class Options(BaseModel):
    study_title: Optional[str] = None
    language: str = "auto"  # auto | vi | en


class InvocationRequest(BaseModel):
    type: Literal["cs", "ux", "meeting"]
    mode: Literal["single"] = "single"  # Route A only; multi-file (Route B) removed.
    files: List[FileItem] = Field(default_factory=list)
    objectives: str = ""
    options: Options = Field(default_factory=Options)


class Transcript(BaseModel):
    """A flat, extracted transcript (one uploaded file)."""
    participant: str
    text: str
    source_name: Optional[str] = None
