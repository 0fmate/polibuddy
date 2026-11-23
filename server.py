"""PoliBuddy server: student and teacher APIs plus the web page.

Run locally:  python -m uvicorn server:app --port 8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from buddy import config, llm, orchestrator, ratelimit, voice
from buddy.catalog import courses
from teacher import crash_test, radar

WEB = Path(__file__).parent / "web"

app = FastAPI(title="PoliBuddy")


class SessionRequest(BaseModel):
    student: str = "demo"
    exercise: str | None = None
    course: str | None = None


class Attachment(BaseModel):
    name: str
    type: str = ""
    data: str  # base64 data URL


class MessageRequest(BaseModel):
    session: str
    text: str = ""
    whiteboard: str | None = None  # PNG as a data URL
    files: list[Attachment] = Field(default_factory=list)


class NextRequest(BaseModel):
    session: str


class CrashTestRequest(BaseModel):
    questions: list[str]


class TranscribeRequest(BaseModel):
    audio: str  # base64 data URL recorded by the browser
    type: str = "audio/webm"


class SpeakRequest(BaseModel):
    text: str


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "?")


def _limit(request: Request) -> None:
    if not ratelimit.allow(_client_ip(request)):
        raise HTTPException(429, "Too many requests: wait a minute and try again.")


def _check_session(sid: str) -> None:
    if sid not in orchestrator.SESSIONS:
        raise HTTPException(404, "Session not found: reload the page.")


@app.get("/api/status")
def status() -> dict:
    using_model = llm.available()
    return {
        "mode": "model" if using_model else "offline",
        "model": config.LLM_MODEL if using_model else None,
        "budget_left": llm.budget_left() if config.llm_configured() else None,
        "vision": llm.vision_available(),
        "stt": voice.stt_available(),
        "tts": voice.tts_available(),
        "last_error": llm.last_error,
        "courses": [{"id": k, "name": v["name"]} for k, v in courses().items()],
    }


@app.post("/api/session")
def session(req: SessionRequest) -> dict:
    return orchestrator.new_session(req.student, req.exercise, req.course)


@app.post("/api/message")
def message(req: MessageRequest, request: Request) -> dict:
    _check_session(req.session)
    _limit(request)
    return orchestrator.message(req.session, req.text, req.whiteboard, [f.model_dump() for f in req.files])


@app.post("/api/next")
def next_exercise(req: NextRequest) -> dict:
    _check_session(req.session)
    return orchestrator.next_exercise(req.session)


@app.get("/api/radar")
def get_radar(course: str = "calculus1") -> dict:
    return radar.aggregate(course)


@app.get("/api/crash-test/demo")
def crash_test_demo(course: str = "calculus1") -> dict:
    return {"questions": crash_test.DEMO_QUESTIONS.get(course, [])}


@app.post("/api/crash-test")
def post_crash_test(req: CrashTestRequest) -> dict:
    return {"report": crash_test.analyze(req.questions)}


@app.post("/api/voice/transcribe")
def voice_transcribe(req: TranscribeRequest, request: Request) -> dict:
    _limit(request)
    text = voice.transcribe(req.audio, req.type)
    if text is None:
        raise HTTPException(503, "Server transcription is not available.")
    return {"text": text}


@app.post("/api/voice/speak")
def voice_speak(req: SpeakRequest, request: Request) -> Response:
    if not voice.tts_available():
        raise HTTPException(503, "Server voice is not available: the browser speaks instead.")
    _limit(request)
    audio = voice.speak(req.text)
    if audio is None:
        raise HTTPException(503, "Server voice is not available: the browser speaks instead.")
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
