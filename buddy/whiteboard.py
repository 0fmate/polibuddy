"""Reads the shared whiteboard (PNG image) with a vision model.

Models can misread handwritten formulas: that is why the text read here is never run directly,
but repeated back to the student for confirmation first.
"""

from __future__ import annotations

from . import config, llm

SYSTEM_PROMPT = r"""Transcribe faithfully what a student handwrote on a digital whiteboard.
Write every formula in LaTeX between $...$ (e.g. $\sin 3x \approx 3x$, $x^3$, $\frac{1 - \cos 2x}{x^2}$).
Do not correct mistakes, do not complete steps, do not add comments.
If the whiteboard is empty or unreadable, reply only: EMPTY"""


def read(png: str) -> str | None:
    """Text read on the whiteboard, or None (no vision model, empty or unreadable)."""
    if not png or not llm.vision_available():
        return None
    content = [llm.image_part(png), {"type": "text", "text": "Transcribe the whiteboard."}]
    text = llm.text(SYSTEM_PROMPT, content, max_tokens=1000, model=config.LLM_VISION_MODEL, effort="")
    if not text or text.strip().upper().startswith("EMPTY"):
        return None
    return text.strip()
