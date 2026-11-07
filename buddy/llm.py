"""Unico punto che parla con il modello linguistico (OpenAI).

Se non c'è una chiave API, o la chiamata fallisce, le funzioni restituiscono None
e il resto del sistema usa le regole offline. Il modello non fa mai i calcoli.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from pydantic import BaseModel

from .config import MODELLO, REASONING_EFFORT, usa_llm  # noqa: F401 (REASONING_EFFORT usato in _extra)

log = logging.getLogger("buddy.llm")

T = TypeVar("T", bound=BaseModel)

_client = None
ultimo_errore: str | None = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(timeout=60.0, max_retries=1)
    return _client


def disponibile() -> bool:
    return usa_llm()


def _extra(effort: str | None = None) -> dict:
    # reasoning_effort vale solo per i modelli di ragionamento: "off" da .env per non inviarlo
    valore = effort or REASONING_EFFORT
    return {} if valore.lower() == "off" else {"reasoning_effort": valore}


def _messaggi(system: str, contenuto: list | str) -> list[dict]:
    return [{"role": "system", "content": system}, {"role": "user", "content": contenuto}]


def strutturato(system: str, contenuto: list | str, schema: type[T], max_tokens: int = 4000) -> T | None:
    """Risposta validata contro uno schema Pydantic (structured outputs)."""
    global ultimo_errore
    if not disponibile():
        return None
    try:
        r = _get_client().chat.completions.parse(
            model=MODELLO,
            messages=_messaggi(system, contenuto),
            response_format=schema,
            max_completion_tokens=max_tokens,
            **_extra(),
        )
        msg = r.choices[0].message
        if msg.refusal or msg.parsed is None:
            ultimo_errore = f"nessuna risposta strutturata (refusal={msg.refusal!r})"
            return None
        ultimo_errore = None
        return msg.parsed
    except Exception as exc:  # rete, chiave, modello, limiti: si torna alle regole offline
        ultimo_errore = f"{type(exc).__name__}: {exc}"
        log.warning("Modello non disponibile, uso le regole offline: %s", ultimo_errore)
        return None


def testo(system: str, contenuto: list | str, max_tokens: int = 2000, effort: str | None = None) -> str | None:
    """Risposta di solo testo. `contenuto` può includere immagini (lavagna, foto)."""
    global ultimo_errore
    if not disponibile():
        return None
    try:
        r = _get_client().chat.completions.create(
            model=MODELLO,
            messages=_messaggi(system, contenuto),
            max_completion_tokens=max_tokens,
            **_extra(effort),
        )
        msg = r.choices[0].message
        if msg.refusal:
            ultimo_errore = f"refusal: {msg.refusal}"
            return None
        ultimo_errore = None
        return (msg.content or "").strip() or None
    except Exception as exc:
        ultimo_errore = f"{type(exc).__name__}: {exc}"
        log.warning("Modello non disponibile, uso le regole offline: %s", ultimo_errore)
        return None


def immagine_png(data_url_o_b64: str) -> dict:
    """Blocco immagine per l'API OpenAI (data URL: PNG della lavagna o foto caricata)."""
    url = data_url_o_b64 if data_url_o_b64.startswith("data:") else f"data:image/png;base64,{data_url_o_b64}"
    return {"type": "image_url", "image_url": {"url": url}}
