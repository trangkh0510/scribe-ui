"""Load the Brain analyzer prompts and fill their per-type placeholders.

Each `app/prompts/<type>.md` has a fenced ``` block under `## SYSTEM PROMPT` and one
under `## USER PROMPT`. The user template's placeholder names differ per type, so
`fill_user` maps the orchestrator's uniform (objectives, context, transcript) onto
each type's slots.
"""
import os
from typing import Tuple

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")
_TYPES = ("ux", "cs", "meeting")


def _extract_block(md: str, heading_prefix: str) -> str:
    """Return the first ```-fenced block after a line starting with heading_prefix."""
    lines = md.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith(heading_prefix)), None)
    if start is None:
        raise ValueError(f"heading {heading_prefix!r} not found")
    # find opening fence
    i = start + 1
    while i < len(lines) and not lines[i].lstrip().startswith("```"):
        i += 1
    if i >= len(lines):
        raise ValueError(f"no fenced block after {heading_prefix!r}")
    body = []
    i += 1
    while i < len(lines) and not lines[i].lstrip().startswith("```"):
        body.append(lines[i])
        i += 1
    return "\n".join(body).strip()


def load_brain_prompt(transcript_type: str) -> Tuple[str, str]:
    if transcript_type not in _TYPES:
        raise ValueError(f"unknown transcript type {transcript_type!r}; expected one of {_TYPES}")
    path = os.path.join(_PROMPT_DIR, f"{transcript_type}.md")
    with open(path, encoding="utf-8") as fh:
        md = fh.read()
    system = _extract_block(md, "## SYSTEM PROMPT")
    user = _extract_block(md, "## USER PROMPT")
    return system, user


def fill_user(transcript_type: str, user_template: str, *,
              objectives: str, context: str, transcript: str) -> str:
    """Substitute the orchestrator's fields into the type's placeholders."""
    out = user_template
    if transcript_type == "ux":
        out = out.replace("{RESEARCH_OBJECTIVES}", objectives)
        out = out.replace("{CONTEXT_DOCUMENT}", context or "Không có")
    elif transcript_type == "cs":
        # cs has no objectives slot — fold objectives into the call context.
        folded = context.strip()
        if objectives.strip():
            folded = (folded + "\n" if folded else "") + f"Mục tiêu/Research questions: {objectives}"
        out = out.replace("{CALL_CONTEXT}", folded or "Không có")
    elif transcript_type == "meeting":
        out = out.replace("{MEETING_AGENDA}", objectives or "")
        out = out.replace("{MEETING_CONTEXT}", context or "Không có")
    out = out.replace("{TRANSCRIPT_CONTENT}", transcript)
    return out
