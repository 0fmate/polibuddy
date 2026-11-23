# PoliBuddy · architecture

```
 Student (web)                     Server (FastAPI, server.py)                         Teacher (web)
 ─────────────                     ───────────────────────────                         ─────────────
 text / whiteboard ─┐
 photo / PDF  ──────┼─► INPUT ─► Interpreter ─► Orchestrator (state machine) ─► Buddy line ─► chat (LaTeX)
 voice (STT) ───────┘   readers   (LLM, JSON)        │            ▲                (draft + LLM      + voice
                                                      ▼            │                 rephrase + check)
                                                 Engine (code: SymPy, mpmath,  ──► table + chart
                                                         our simulators)
                                                      │
                                                      ▼
                                              Memory (anonymous outcomes) ─► Radar · Crash Test ─► dashboard
```

The language model only does two things: **understand** the student's plan and **phrase** the buddy's lines.
Every number, every verdict and every decision about how much help to give comes from deterministic code.

## Input
- **Text** typed in the chat (`POST /api/message`).
- **Whiteboard** PNG → `buddy/whiteboard.py` (a vision model transcribes it, formulas in LaTeX).
- **Attachments** → `buddy/attachments.py`: images read by a vision model, PDFs with pypdf (offline too), text/code files decoded.
- **Voice** → `buddy/voice.py`: server speech-to-text (e.g. Whisper on Groq) or the browser's own recognition; the transcript enters the same pipeline as text.

Whatever is read is always repeated back to the student ("…, right?") before it runs, so a misread plan never becomes the student's mistake.

## Knowledge
- `data/catalog.yaml`: courses, concepts (with keywords), exercises, **typical mistakes** (the wrong plan, a targeted question, a hint), offline rules, slides. Parameters per student (from a hash of the student ID).
- The exercise's true answer stays on the server; it is never sent to the browser or to the model's lines.

## Tools (all deterministic code)
| Tool | File | What it does |
| --- | --- | --- |
| `interpret` | `buddy/interpreter.py` | LLM structured output (`Plan`, Pydantic): substitutions or proposed value, paraphrase. Offline: catalog rules. |
| `run` (limit) | `buddy/engine.py` | Applies the substitution with SymPy, computes the limit, evaluates the true function near 0 with mpmath at 60 digits. |
| `run` (value) | `buddy/engine.py` | Evaluates what the proposed value implies (e.g. the height of the ball at the proposed landing time). |
| `run` (trace) | `buddy/engine.py` | Runs the program with our own Python simulator, step by step (never the student's code). |
| `rephrase` + `is_safe` | `buddy/companion.py` | The LLM rephrases the drafted line; rejected if it contains forbidden content or changes any number. |
| `aggregate`, `analyze` | `teacher/` | Aggregates anonymous outcomes per course; matches exam questions to concepts. |

## Decisions (in code, not in the prompt)
- **State machine** (`buddy/orchestrator.py`): `awaiting_plan` → `awaiting_confirmation` → run → `solved`, or back to `awaiting_plan`.
- **How much help:** after each failed plan the help level grows: 1 contradiction, 2 targeted question from the catalog, 3 slide, 4 hint. Never the solution.
- **Boundary:** requests for the solution are caught by a regex before any model call and answered with "Let's try your idea first".
- **Privacy:** only anonymous outcomes (hashed ID, exercise, mistake, attempts, outcome); the teacher sees aggregates above 10 sessions.
- **Fallback:** if the model fails, there is no key or the daily budget is used up, offline rules take over; the demo never stops.

## LLM layer (`buddy/llm.py`)
- Any **OpenAI-compatible** provider through `LLM_BASE_URL` (Groq, Google Gemini, OpenRouter, OpenAI, a local Ollama...).
- Structured output: native JSON schema first; providers that do not support it get JSON mode with the schema in the prompt, validated with Pydantic.
- Formulas: the model writes `[[ascii maths]]` (no backslashes, which models tend to break inside JSON); `buddy/formulas.py` converts them to LaTeX.
- Public demo protection: per-IP rate limit on the AI endpoints (`buddy/ratelimit.py`) and a daily cap on model calls, after which the app runs on offline rules until the next day.

## Output
- Chat lines with formulas in LaTeX (rendered with KaTeX), spoken in voice mode (server TTS if configured, otherwise the browser's speech synthesis), transcript downloadable.
- Results panel: predicted vs real value, table, chart, verdict; mascot state and progress per topic.
- Teacher dashboard: KPIs, outcomes by exercise, mistakes to review, Crash Test report.

## Libraries
Python: FastAPI, Uvicorn, OpenAI SDK (as a generic client), SymPy, mpmath, Pydantic, PyYAML, pypdf, pytest.
Front end: plain HTML/CSS/JS + KaTeX, no build step.
