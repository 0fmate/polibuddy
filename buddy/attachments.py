"""Photos and documents the student uploads in the chat.

- images: read by the vision model (without one they cannot be read);
- PDFs: text extracted with pypdf (works offline too, not for scanned PDFs);
- text and code files: read directly.
What is read is added to the plan and repeated back to the student before running it.
"""

from __future__ import annotations

import base64
import binascii
import io
from dataclasses import dataclass

from . import config, llm

MAX_BYTES = 8 * 1024 * 1024
MAX_CHARS = 4000
_TEXT_EXTENSIONS = (".txt", ".md", ".py", ".csv", ".json", ".c", ".java", ".m", ".tex")

SYSTEM_PROMPT = r"""A student uploaded a photo or image (notes, a worked exercise, code, formulas).
Transcribe the relevant content faithfully: text, formulas in LaTeX between $...$ (e.g. $\sin 3x \approx 3x$, $x^3$),
code. Do not correct mistakes, do not complete steps, do not add comments.
If the image contains nothing readable, reply only: EMPTY"""


@dataclass
class Reading:
    name: str
    text: str | None
    note: str

    def public(self) -> dict:
        summary = (self.text or "")[:220] + ("…" if self.text and len(self.text) > 220 else "")
        return {"name": self.name, "ok": self.text is not None, "summary": summary, "note": self.note}


def _decode(data: str) -> bytes | None:
    try:
        raw = data.split(",", 1)[1] if data.startswith("data:") else data
        return base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError, IndexError):
        return None


def _read_image(name: str, data: str) -> Reading:
    if not llm.vision_available():
        return Reading(name, None, "image reading is not available here: please type your plan")
    text = llm.text(SYSTEM_PROMPT, [llm.image_part(data), {"type": "text", "text": "Transcribe the content."}],
                    max_tokens=1500, model=config.LLM_VISION_MODEL, effort="")
    if not text or text.strip().upper().startswith("EMPTY"):
        return Reading(name, None, "I could not read anything in this image")
    return Reading(name, text.strip()[:MAX_CHARS], "read by the model")


def _read_pdf(name: str, content: bytes) -> Reading:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:5]).strip()
    except Exception:  # noqa: BLE001 - damaged or encrypted PDF
        return Reading(name, None, "I cannot open this PDF")
    if not text:
        return Reading(name, None, "PDF without selectable text (a scan): upload a photo of the page instead")
    return Reading(name, text[:MAX_CHARS], "text extracted from the PDF")


def read(files: list[dict]) -> list[Reading]:
    readings: list[Reading] = []
    for f in files[:5]:
        name = str(f.get("name", "file"))[:80]
        mime = str(f.get("type", ""))
        data = str(f.get("data", ""))
        content = _decode(data)
        if content is None:
            readings.append(Reading(name, None, "unreadable file"))
        elif len(content) > MAX_BYTES:
            readings.append(Reading(name, None, "file too large (8 MB max)"))
        elif mime.startswith("image/"):
            readings.append(_read_image(name, data))
        elif mime == "application/pdf" or name.lower().endswith(".pdf"):
            readings.append(_read_pdf(name, content))
        elif mime.startswith("text/") or name.lower().endswith(_TEXT_EXTENSIONS):
            text = content.decode("utf-8", errors="replace").strip()
            readings.append(Reading(name, text[:MAX_CHARS] or None, "text file"))
        else:
            readings.append(Reading(name, None, "file type not supported (use images, PDF or text)"))
    return readings


def as_text(readings: list[Reading]) -> str:
    return "\n".join(f"(Content of {r.name}: {r.text})" for r in readings if r.text)
