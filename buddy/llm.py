"""The only place that talks to the language model.

Works with any OpenAI-compatible provider (Groq, Google Gemini, OpenRouter, OpenAI...) through
`LLM_BASE_URL`. If there is no key, the daily budget is used up, or a call fails, the functions
return None and the rest of the app falls back to the offline rules. The model never does the maths.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from . import config

log = logging.getLogger("polibuddy.llm")

T = TypeVar("T", bound=BaseModel)

_client = None
_lock = threading.Lock()
_calls_today = 0
_today = dt.date.today()
last_error: str | None = None


def client():
    global _client
    if _client is None:
        from openai import OpenAI

        kwargs = {"api_key": config.LLM_API_KEY, "timeout": 60.0, "max_retries": 1}
        if config.LLM_BASE_URL:
            kwargs["base_url"] = config.LLM_BASE_URL
        _client = OpenAI(**kwargs)
    return _client


def budget_left() -> int:
    with _lock:
        if dt.date.today() != _today:
            return config.DAILY_LLM_CALLS
        return max(0, config.DAILY_LLM_CALLS - _calls_today)


def available() -> bool:
    """A model can be used right now (key configured and daily budget not exhausted)."""
    return config.llm_configured() and budget_left() > 0


def count_call() -> None:
    global _calls_today, _today
    with _lock:
        if dt.date.today() != _today:
            _today, _calls_today = dt.date.today(), 0
        _calls_today += 1


def _extra(effort: str | None) -> dict:
    value = config.LLM_REASONING_EFFORT if effort is None else effort
    return {"reasoning_effort": value} if value and value.lower() != "off" else {}


def _messages(system: str, content: list | str) -> list[dict]:
    return [{"role": "system", "content": system}, {"role": "user", "content": content}]


def _fail(exc: Exception) -> None:
    global last_error
    last_error = f"{type(exc).__name__}: {exc}"[:500]
    log.warning("Model call failed, using the offline rules: %s", last_error)


def structured(system: str, content: list | str, schema: type[T], max_tokens: int = 4000) -> T | None:
    """Reply validated against a Pydantic schema.

    First tries native structured outputs (JSON schema); providers that do not support them
    get JSON mode with the schema in the prompt, and the reply is validated here.
    """
    global last_error
    if not available():
        return None
    count_call()
    try:
        r = client().chat.completions.parse(
            model=config.LLM_MODEL,
            messages=_messages(system, content),
            response_format=schema,
            max_completion_tokens=max_tokens,
            **_extra(None),
        )
        msg = r.choices[0].message
        if msg.parsed is not None and not msg.refusal:
            last_error = None
            return msg.parsed
    except Exception as exc:  # noqa: BLE001 - unsupported json_schema, network, limits...
        log.info("Native structured output unavailable (%s), trying JSON mode", type(exc).__name__)

    if not available():
        return None
    count_call()
    schema_text = json.dumps(schema.model_json_schema())
    try:
        r = client().chat.completions.create(
            model=config.LLM_MODEL,
            messages=_messages(f"{system}\n\nReply ONLY with a JSON object that follows this JSON schema:\n{schema_text}",
                               content),
            response_format={"type": "json_object"},
            max_completion_tokens=max_tokens,
            **_extra(None),
        )
        parsed = schema.model_validate_json(r.choices[0].message.content or "")
        last_error = None
        return parsed
    except (ValidationError, Exception) as exc:  # noqa: BLE001
        _fail(exc)
        return None


def text(system: str, content: list | str, max_tokens: int = 2000, effort: str | None = None,
         model: str | None = None) -> str | None:
    """Plain-text reply. `content` may include images (whiteboard, photos) with a vision model."""
    global last_error
    if not available():
        return None
    count_call()
    try:
        r = client().chat.completions.create(
            model=model or config.LLM_MODEL,
            messages=_messages(system, content),
            max_completion_tokens=max_tokens,
            **_extra(effort),
        )
        msg = r.choices[0].message
        if getattr(msg, "refusal", None):
            last_error = f"refusal: {msg.refusal}"
            return None
        last_error = None
        return (msg.content or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
        return None


def image_part(data_url_or_b64: str) -> dict:
    """Image block for the OpenAI-compatible API (data URL: whiteboard PNG or uploaded photo)."""
    url = data_url_or_b64 if data_url_or_b64.startswith("data:") else f"data:image/png;base64,{data_url_or_b64}"
    return {"type": "image_url", "image_url": {"url": url}}


def vision_available() -> bool:
    return available() and bool(config.LLM_VISION_MODEL)
