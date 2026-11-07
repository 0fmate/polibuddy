"""Server di PoliBuddy: API per studente e docente + pagina web.

Avvio:  .venv\\Scripts\\python -m uvicorn server:app --port 8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from buddy import llm, orchestrator, voce
from buddy.catalogo import corsi
from buddy.config import MODELLO
from docente import crash_test, radar

WEB = Path(__file__).parent / "web"

app = FastAPI(title="PoliBuddy")


class RichiestaSessione(BaseModel):
    studente: str = "demo"
    esercizio: str | None = None
    corso: str | None = None


class Allegato(BaseModel):
    nome: str
    tipo: str = ""
    dati: str  # data URL base64


class RichiestaMessaggio(BaseModel):
    sessione: str
    testo: str = ""
    lavagna: str | None = None  # PNG come data URL
    allegati: list[Allegato] = []


class RichiestaProssimo(BaseModel):
    sessione: str


class RichiestaCrashTest(BaseModel):
    domande: list[str]


class RichiestaTrascrivi(BaseModel):
    audio: str  # data URL base64 recorded by the browser
    tipo: str = "audio/webm"


class RichiestaParla(BaseModel):
    testo: str


def _sessione_esiste(sid: str) -> None:
    if sid not in orchestrator.SESSIONI:
        raise HTTPException(404, "Session not found: reload the page.")


@app.get("/api/stato")
def stato() -> dict:
    return {
        "modalita": "modello" if llm.disponibile() else "offline",
        "modello": MODELLO if llm.disponibile() else None,
        "ultimo_errore": llm.ultimo_errore,
        "corsi": [{"id": k, "nome": v["nome"]} for k, v in corsi().items()],
    }


@app.post("/api/sessione")
def sessione(req: RichiestaSessione) -> dict:
    return orchestrator.nuova_sessione(req.studente, req.esercizio, req.corso)


@app.post("/api/messaggio")
def messaggio(req: RichiestaMessaggio) -> dict:
    _sessione_esiste(req.sessione)
    return orchestrator.messaggio(req.sessione, req.testo, req.lavagna, [a.model_dump() for a in req.allegati])


@app.post("/api/prossimo")
def prossimo(req: RichiestaProssimo) -> dict:
    _sessione_esiste(req.sessione)
    return orchestrator.prossimo(req.sessione)


@app.get("/api/radar")
def get_radar(corso: str = "analisi1") -> dict:
    return radar.aggrega(corso)


@app.get("/api/crash-test/demo")
def crash_test_demo(corso: str = "analisi1") -> dict:
    return {"domande": crash_test.DOMANDE_DEMO.get(corso, [])}


@app.post("/api/crash-test")
def post_crash_test(req: RichiestaCrashTest) -> dict:
    return {"report": crash_test.analizza(req.domande)}


@app.post("/api/voce/trascrivi")
def voce_trascrivi(req: RichiestaTrascrivi) -> dict:
    testo = voce.trascrivi(req.audio, req.tipo)
    if testo is None:
        raise HTTPException(503, "Voice transcription is not available (no model or audio not understood).")
    return {"testo": testo}


@app.post("/api/voce/parla")
def voce_parla(req: RichiestaParla) -> Response:
    audio = voce.parla(req.testo)
    if audio is None:
        raise HTTPException(503, "Voice synthesis is not available.")
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
