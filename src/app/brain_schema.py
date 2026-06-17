"""Pydantic schemas mirroring the 3 Brain analyzer JSON outputs (ux / cs / meeting).

Field names and severity/level literals match the schemas defined in
`app/prompts/{ux,cs,meeting}.md` exactly, so a validated object renders cleanly
through `app/render/render.py`.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel


class MetaField(BaseModel):
    label: str
    value: str


class Meta(BaseModel):
    title: str = ""
    subtitle: str = ""
    fields: List[MetaField] = []


class Quote(BaseModel):
    text: str = ""
    ctx: str = ""


class Score(BaseModel):
    name: str = ""
    note: str = ""
    score: int = 0


class Action(BaseModel):
    task: str = ""
    owner: str = ""
    deadline: str = ""


# ---------- UX ----------
class UxFinding(BaseModel):
    tag: str = ""
    text: str = ""
    evidence: str = ""  # verbatim ≤15-word transcript quote backing the finding


class UxPainPoint(BaseModel):
    pp: str = ""
    severity: Literal["high", "medium", "low"] = "low"
    flow: str = ""
    evidence: str = ""  # verbatim ≤15-word transcript quote backing the pain point


class UxVerdict(BaseModel):
    level: Literal["pass", "fail"] = "pass"
    label: str = ""
    reason: str = ""


class UxReport(BaseModel):
    mode: Literal["ux"]
    meta: Meta
    findings: List[UxFinding] = []
    painPoints: List[UxPainPoint] = []
    quotes: List[Quote] = []
    verdict: UxVerdict
    scores: List[Score] = []
    scoreTotal: int = 0
    suggestions: List[str] = []


# ---------- CS ----------
class CsSentiment(BaseModel):
    phase: str = ""
    level: Literal["neg", "neu", "pos"] = "neu"
    label: str = ""
    signal: str = ""


class CsIssue(BaseModel):
    issue: str = ""
    severity: Literal["crit", "major", "minor"] = "minor"
    status: str = ""


class CsMeetingVerdict(BaseModel):
    level: Literal["pass", "warn", "fail"] = "pass"
    label: str = ""
    reason: str = ""


class CsReport(BaseModel):
    mode: Literal["cs"]
    meta: Meta
    summary: str = ""
    sentiment: List[CsSentiment] = []
    sentimentConclusion: str = ""
    issues: List[CsIssue] = []
    actions: List[Action] = []
    quotes: List[Quote] = []
    verdict: CsMeetingVerdict
    scores: List[Score] = []
    scoreTotal: int = 0
    suggestions: List[str] = []


# ---------- MEETING ----------
class MeetingDecision(BaseModel):
    text: str = ""
    who: str = ""


class MeetingReport(BaseModel):
    mode: Literal["meeting"]
    meta: Meta
    summary: str = ""
    decisions: List[MeetingDecision] = []
    actions: List[Action] = []
    offtopic: List[str] = []
    verdict: CsMeetingVerdict
    scores: List[Score] = []
    scoreTotal: int = 0
    suggestions: List[str] = []


BRAIN_SCHEMA = {"ux": UxReport, "cs": CsReport, "meeting": MeetingReport}


def is_too_short_error(data: dict) -> bool:
    """The Brain prompts may return {"error":"transcript_too_short",...} instead of a report."""
    return isinstance(data, dict) and data.get("error") == "transcript_too_short"
