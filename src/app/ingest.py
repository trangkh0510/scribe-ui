import base64
import binascii
import io
import os
from dataclasses import dataclass, field
from docx import Document
from pypdf import PdfReader
from app.models import Transcript


@dataclass
class IngestResult:
    transcripts: list[Transcript] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _extract_txt(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


_EXTRACTORS = {".txt": _extract_txt, ".docx": _extract_docx, ".pdf": _extract_pdf}


def ingest(payload: dict) -> IngestResult:
    result = IngestResult()

    for item in payload.get("files") or []:
        name = item.get("name", "")
        ext = os.path.splitext(name)[1].lower()
        extractor = _EXTRACTORS.get(ext)
        if extractor is None:
            result.warnings.append(f"skipped {name or '<unnamed>'}: unsupported type")
            continue
        try:
            raw = base64.b64decode(item.get("content_base64", ""), validate=True)
            text = extractor(raw)
        except (binascii.Error, ValueError, KeyError) as exc:
            result.warnings.append(f"skipped {name or '<unnamed>'}: {exc}")
            continue
        if not text.strip():
            result.warnings.append(f"skipped {name or '<unnamed>'}: no extractable text")
            continue
        participant = item.get("participant") or os.path.splitext(name)[0] or "Unknown"
        result.transcripts.append(
            Transcript(participant=participant, text=text, source_name=name or None)
        )

    for item in payload.get("transcripts") or []:
        text = item.get("text", "")
        if not text.strip():
            continue
        result.transcripts.append(
            Transcript(participant=item.get("participant") or "Unknown", text=text)
        )

    return result
