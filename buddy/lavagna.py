"""Legge la lavagna condivisa (immagine PNG) con il modello multimodale.

I modelli possono leggere male le formule scritte a mano: per questo il testo letto
non viene mai eseguito direttamente, ma ripetuto allo studente per conferma.
"""

from __future__ import annotations

from . import llm

SYSTEM_LAVAGNA = r"""Transcribe faithfully what a student handwrote on a digital whiteboard.
Write every formula in LaTeX between $...$ (e.g. $\sin 3x \approx 3x$, $x^3$, $\frac{1 - \cos 2x}{x^2}$).
Do not correct mistakes, do not complete steps, do not add comments.
If the whiteboard is empty or unreadable, reply only: EMPTY"""


def leggi(png: str) -> str | None:
    """Testo letto sulla lavagna, oppure None (offline, vuota o illeggibile)."""
    if not png or not llm.disponibile():
        return None
    contenuto = [llm.immagine_png(png), {"type": "text", "text": "Transcribe the whiteboard."}]
    letto = llm.testo(SYSTEM_LAVAGNA, contenuto, max_tokens=1000)
    if not letto or letto.strip().upper().startswith("EMPTY"):
        return None
    return letto.strip()
