"""Voice conversation with PoliBuddy.

Speech-to-text and text-to-speech go through the provider when `STT_MODEL` / `TTS_MODEL` are set
(e.g. Groq's Whisper for STT); otherwise the browser's own speech recognition and synthesis are used.
The voice goes through the same pipeline as the chat: transcript -> interpreter -> engine -> buddy line.
Formulas written in LaTeX are turned into words before being spoken.
"""

from __future__ import annotations

import base64
import re

from . import config, llm

_VOICE_STYLE = "You are a friendly study buddy talking to a first-year student. Warm, upbeat, clear, not too fast."
_STT_PROMPT = (
    "A student explains how to solve a calculus, physics or programming exercise. "
    "Terms: sine, cosine, tangent, Taylor, limit, x cubed, v zero over g, range, while loop."
)


def stt_available() -> bool:
    return llm.available() and bool(config.STT_MODEL)


def tts_available() -> bool:
    return llm.available() and bool(config.TTS_MODEL)


def transcribe(data: str, mime: str = "audio/webm") -> str | None:
    """Speech-to-text. `data` is a base64 data URL recorded by the browser."""
    if not stt_available():
        return None
    try:
        raw = base64.b64decode(data.split(",", 1)[1] if data.startswith("data:") else data)
        ext = next((e for key, e in (("mpeg", "mp3"), ("mp3", "mp3"), ("mp4", "mp4"), ("m4a", "m4a"),
                                     ("ogg", "ogg"), ("wav", "wav")) if key in mime), "webm")
        llm.count_call()
        r = llm.client().audio.transcriptions.create(
            model=config.STT_MODEL, file=(f"voice.{ext}", raw, mime.split(";")[0]), language="en", prompt=_STT_PROMPT,
        )
        return (r.text or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        llm.last_error = f"STT {type(exc).__name__}: {exc}"[:500]
        return None


_REPLACEMENTS = [
    (r"\\displaystyle", " "),
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


def latex_to_words(text: str) -> str:
    """'$\\frac{v_0}{g}$' -> 'v zero over g': what a voice can read out loud."""
    t = text
    for _ in range(3):  # nested fractions
        t = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r" \1 over \2 ", t)
    t = re.sub(r"\\sqrt\{([^{}]*)\}", r" the square root of \1 ", t)
    for pattern, repl in _REPLACEMENTS:
        t = re.sub(pattern, repl, t)
    t = t.replace("$", "").replace("{", "").replace("}", "").replace("\\", "")
    t = t.replace("←", "").replace("…", "...").replace("—", ", ")
    return re.sub(r"\s+", " ", t).strip()


def speak(text: str) -> bytes | None:
    """Text-to-speech: mp3 of PoliBuddy's line, or None (the browser speaks instead)."""
    if not tts_available():
        return None
    try:
        llm.count_call()
        r = llm.client().audio.speech.create(
            model=config.TTS_MODEL, voice=config.TTS_VOICE, input=latex_to_words(text)[:3000],
            instructions=_VOICE_STYLE, response_format="mp3",
        )
        return r.read()
    except Exception as exc:  # noqa: BLE001
        llm.last_error = f"TTS {type(exc).__name__}: {exc}"[:500]
        return None
