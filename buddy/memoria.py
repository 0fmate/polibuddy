"""Memoria strutturata: profilo per studente ed esiti anonimi delle sessioni.

Non si salva la chat: solo quale esercizio, quale errore tipico, quanti tentativi e l'esito.
Lo studente è identificato da un'impronta (hash), mai dal nome o dalla matricola.
"""

from __future__ import annotations

import hashlib
import json
import time

from .config import RUNTIME_DIR

ESITI = ["da_solo", "dopo_domanda", "dopo_slide", "con_spunto", "non_risolto"]


def anonimo(studente: str) -> str:
    return hashlib.sha256(studente.strip().lower().encode()).hexdigest()[:12]


def esito_da_livello(livello_aiuto: int) -> str:
    """Quanto aiuto è servito prima che il piano tornasse."""
    if livello_aiuto <= 1:
        return "da_solo"
    return {2: "dopo_domanda", 3: "dopo_slide"}.get(livello_aiuto, "con_spunto")


def _file_profilo(studente: str):
    return RUNTIME_DIR / "studenti" / f"{anonimo(studente)}.json"


def profilo(studente: str) -> dict:
    f = _file_profilo(studente)
    p = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    p.setdefault("risolti", [])
    p.setdefault("esiti", {})
    p.setdefault("tentati", [])
    return p


def _salva(studente: str, p: dict) -> None:
    f = _file_profilo(studente)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")


def segna_tentato(studente: str, id_esercizio: str) -> None:
    p = profilo(studente)
    if id_esercizio not in p["tentati"]:
        p["tentati"].append(id_esercizio)
        _salva(studente, p)


def segna_risolto(studente: str, id_esercizio: str, esito: str = "da_solo") -> None:
    p = profilo(studente)
    if id_esercizio not in p["risolti"]:
        p["risolti"].append(id_esercizio)
    precedente = p["esiti"].get(id_esercizio)
    # si tiene il risultato migliore: "da solo" batte "con aiuto"
    if precedente is None or ESITI.index(esito) < ESITI.index(precedente):
        p["esiti"][id_esercizio] = esito
    _salva(studente, p)


def stato_argomento(p: dict, id_esercizio: str) -> str:
    """da_fare | in_corso | con_aiuto | da_solo: l'avanzamento per argomento mostrato in chat."""
    esito = p["esiti"].get(id_esercizio)
    if esito == "da_solo":
        return "da_solo"
    if esito:
        return "con_aiuto"
    if id_esercizio in p["tentati"]:
        return "in_corso"
    return "da_fare"


def registra_sessione(studente: str, esercizio: str, tipo: str, concetti: list[str],
                      errore: str | None, tentativi: int, esito: str) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    riga = {
        "studente": anonimo(studente),
        "esercizio": esercizio,
        "tipo": tipo,
        "concetti": concetti,
        "errore": errore,
        "tentativi": tentativi,
        "esito": esito,
        "ts": int(time.time()),
        "simulata": False,
    }
    with (RUNTIME_DIR / "sessioni.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(riga, ensure_ascii=False) + "\n")


def sessioni_reali() -> list[dict]:
    f = RUNTIME_DIR / "sessioni.jsonl"
    if not f.exists():
        return []
    return [json.loads(r) for r in f.read_text(encoding="utf-8").splitlines() if r.strip()]


def log_passo(sessione: str, evento: str, dati: dict) -> None:
    """Ogni passo registrato: serve per il debug e come prova nei test."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    riga = {"ts": round(time.time(), 3), "sessione": sessione, "evento": evento, **dati}
    with (RUNTIME_DIR / "log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(riga, ensure_ascii=False, default=str) + "\n")
