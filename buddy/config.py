"""Settings: read from `.env` (if present) and from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RUNTIME_DIR = DATA_DIR / "runtime"
CATALOG_PATH = DATA_DIR / "catalog.yaml"


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


# --- Language model: any OpenAI-compatible provider (Groq, Gemini, OpenRouter, OpenAI...) ---
LLM_API_KEY = _env("LLM_API_KEY") or _env("OPENAI_API_KEY")
LLM_BASE_URL = _env("LLM_BASE_URL")  # empty = OpenAI
LLM_MODEL = _env("LLM_MODEL", "openai/gpt-oss-120b")
LLM_VISION_MODEL = _env("LLM_VISION_MODEL")  # for whiteboard and photos; empty = image reading off
LLM_REASONING_EFFORT = _env("LLM_REASONING_EFFORT")  # only for reasoning models (e.g. "low"); empty = not sent
STT_MODEL = _env("STT_MODEL")  # speech-to-text; empty = the browser's speech recognition
TTS_MODEL = _env("TTS_MODEL")  # text-to-speech; empty = the browser's speech synthesis
TTS_VOICE = _env("TTS_VOICE", "alloy")

# "auto" uses the model when a key is set, otherwise the offline rules. "offline" = always rules.
MODE = _env("BUDDY_MODE", "auto").lower()
REPHRASE = _env("BUDDY_REPHRASE", "1") != "0"

# --- Public demo protection ---
RATE_LIMIT_PER_MINUTE = int(_env("RATE_LIMIT_PER_MINUTE", "12"))  # requests per IP to the AI endpoints
DAILY_LLM_CALLS = int(_env("DAILY_LLM_CALLS", "600"))  # past this, the app switches to offline rules until tomorrow

# Teacher view: below this number of sessions a figure is not shown.
MIN_SESSIONS = int(_env("BUDDY_MIN_SESSIONS", "10"))

# How much help: levels after each failed plan.
# 1 = contradiction, 2 = targeted question, 3 = slide, 4 = hint.
MAX_HELP_LEVEL = 4

# Points where the engine evaluates the function, getting closer to zero.
TABLE_POINTS = ["0.1", "0.01", "0.001", "0.0001"]
# mpmath precision: with ordinary floats the numerator vanishes for small x.
PRECISION_DIGITS = 60


def llm_configured() -> bool:
    return MODE != "offline" and bool(LLM_API_KEY)
