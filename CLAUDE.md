# PoliBuddy: instructions for coding agents

Prototype for the Reply Student Tech Clash 2026 (AI on Campus). Python + FastAPI, static web page in `web/`.
Everything the user sees is in English.

## Project rules
- The language model (OpenAI) understands the student's plan and gives the buddy its voice, but **never does the maths**: numbers come from `buddy/esecutore.py` (SymPy + high-precision mpmath, our own simulators).
- The session phases and "how much help to give" are decided by `buddy/orchestrator.py`, not by the model.
- The buddy never gives the solution: the check is in code (`buddy/compagno.py`), not only in the prompt.
- Formulas: the model writes ASCII maths between [[ ]] in structured outputs (no backslashes in JSON); `buddy/formule.py` turns it into $LaTeX$, the browser renders it with KaTeX.
- Everything must also work without an API key (offline rules in the catalogue). Do not break this mode.
- Exercises and typical mistakes live in `data/catalogo.yaml`: add exercises there, not in code.
- Teacher data is anonymous and aggregated, above the `BUDDY_SOGLIA` threshold.

## How to work
- Small steps, one feature at a time. Explain architectural changes before making them.
- After every change: `.venv\Scripts\python -m pytest -q`.
- Start: `.venv\Scripts\python -m uvicorn server:app --port 8000` (or `avvia.bat`).
- Never put API keys in code or chat: only in `.env` (excluded from git).
