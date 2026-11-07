"""Voice conversation with PoliBuddy (OpenAI speech-to-text and text-to-speech).

The voice goes through the same pipeline as the chat: transcript -> interpreter -> engine -> buddy line.
Formulas written in LaTeX are turned into words before being spoken.
"""

from __future__ import annotations

import base64
import os
import re

from . import llm

MODELLO_STT = os.environ.get("BUDDY_STT_MODEL", "gpt-4o-mini-transcribe")
MODELLO_TTS = os.environ.get("BUDDY_TTS_MODEL", "gpt-4o-mini-tts")
VOCE = os.environ.get("BUDDY_VOICE", "coral")

_ISTRUZIONI_VOCE = "You are a friendly study buddy talking to a first-year student. Warm, upbeat, clear, not too fast."
_SUGGERIMENTO_STT = (
    "A student explains how to solve a calculus, physics or programming exercise. "
    "Terms: sine, cosine, tangent, Taylor, limit, x cubed, v zero over g, range, while loop."
)


def trascrivi(dati: str, mime: str = "audio/webm") -> str | None:
    """Speech-to-text. `dati` is a base64 data URL recorded by the browser."""
    if not llm.disponibile():
        return None
    try:
        grezzo = base64.b64decode(dati.split(",", 1)[1] if dati.startswith("data:") else dati)
        est = next((e for chiave, e in (("mpeg", "mp3"), ("mp3", "mp3"), ("mp4", "mp4"), ("m4a", "m4a"),
                                            ("ogg", "ogg"), ("wav", "wav")) if chiave in mime), "webm")
        r = llm._get_client().audio.transcriptions.create(
            model=MODELLO_STT, file=(f"voce.{est}", grezzo, mime.split(";")[0]), language="en",
            prompt=_SUGGERIMENTO_STT,
        )
        return (r.text or "").strip() or None
    except Exception as exc:
        llm.ultimo_errore = f"STT {type(exc).__name__}: {exc}"
        return None


_SOSTITUZIONI = [
    (r"\\lim_\{x\s*\\to\s*0\}", " the limit as x goes to zero of "),
    (r"\\to", " goes to "),
    (r"\\approx", " is about "),
    (r"\\cdot|\\times", " times "),
    (r"\\sin", " sine of "),
    (r"\\cos", " cosine of "),
    (r"\\tan", " tangent of "),
    (r"\\lceil|\\rceil", " "),
    (r"\\mathrm\{m/s\^2\}", " meters per second squared "),
    (r"\\mathrm\{m/s\}", " meters per second "),
    (r"\\mathrm\{m\}", " meters "),
    (r"\\,|\\ |~", " "),
    (r"v_0|v_\{0\}", " v zero "),
    (r"\^\{?2\}?", " squared "),
    (r"\^\{?3\}?", " cubed "),
    (r"\^\{([^}]*)\}", r" to the \1 "),
]


def latex_a_parole(testo: str) -> str:
    """'$\\frac{v_0}{g}$' -> 'v zero over g': what the voice can read out loud."""
    t = testo
    for _ in range(3):  # frazioni annidate
        t = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r" \1 over \2 ", t)
    t = re.sub(r"\\sqrt\{([^{}]*)\}", r" the square root of \1 ", t)
    for schema, sost in _SOSTITUZIONI:
        t = re.sub(schema, sost, t)
    t = t.replace("$", "").replace("{", "").replace("}", "").replace("\\", "")
    t = t.replace("←", "").replace("…", "...").replace("—", ", ")
    return re.sub(r"\s+", " ", t).strip()


def parla(testo: str) -> bytes | None:
    """Text-to-speech: mp3 of PoliBuddy's line."""
    if not llm.disponibile():
        return None
    try:
        r = llm._get_client().audio.speech.create(
            model=MODELLO_TTS, voice=VOCE, input=latex_a_parole(testo)[:3000],
            instructions=_ISTRUZIONI_VOCE, response_format="mp3",
        )
        return r.read()
    except Exception as exc:
        llm.ultimo_errore = f"TTS {type(exc).__name__}: {exc}"
        return None
