@echo off
REM Starts the demo on http://localhost:8000
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements-dev.txt
)
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn server:app --port 8000
