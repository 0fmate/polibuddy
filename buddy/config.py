"""Configurazione: legge .env (se c'è) e le variabili d'ambiente."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RUNTIME_DIR = DATA_DIR / "runtime"
CATALOGO_PATH = DATA_DIR / "catalogo.yaml"


def _carica_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for riga in env.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, valore = riga.split("=", 1)
        os.environ.setdefault(chiave.strip(), valore.strip().strip('"').strip("'"))


_carica_env()

# Modello OpenAI: il default è quello degli esempi degli organizzatori; si cambia da .env.
MODELLO = os.environ.get("BUDDY_MODEL", "gpt-6-luna")
# Ragionamento del modello (gpt-6-luna accetta none/low/medium/high/xhigh). "off" = non inviato.
# L'interprete ragiona un po' ("low"); le battute del compagno sono solo riformulazioni ("none").
REASONING_EFFORT = os.environ.get("BUDDY_REASONING_EFFORT", "").strip() or "low"
REASONING_EFFORT_COMPAGNO = os.environ.get("BUDDY_REASONING_EFFORT_COMPAGNO", "").strip() or "none"
# "auto" usa il modello se c'è una chiave, altrimenti le regole offline.
MODALITA = os.environ.get("BUDDY_MODE", "auto").lower()

# Soglia minima di sessioni sotto cui il docente non vede il dato.
SOGLIA_RADAR = int(os.environ.get("BUDDY_SOGLIA", "10"))

# Quanta corda: livelli di aiuto dopo ogni tentativo fallito.
# 1 = contraddizione + "dove l'abbiamo perso?", 2 = domanda mirata, 3 = slide, 4 = spunto.
LIVELLO_AIUTO_MAX = 4

# Punti in cui il compagno calcola i valori (avvicinandosi a zero).
PUNTI_TABELLA = ["0.1", "0.01", "0.001", "0.0001"]
# Precisione di mpmath: con i float normali il numeratore sparisce per x piccoli.
PRECISIONE_CIFRE = 60


def usa_llm() -> bool:
    if MODALITA == "offline":
        return False
    return bool(os.environ.get("OPENAI_API_KEY"))
