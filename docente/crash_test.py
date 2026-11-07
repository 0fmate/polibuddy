"""Crash Test sui dati: la bozza d'esame contro gli errori raccolti nel semestre.

Collega ogni domanda ai concetti del catalogo (per parole chiave) e riporta cosa dicono
le sessioni su quei concetti. Decide sempre il docente.
"""

from __future__ import annotations

import re

from buddy.catalogo import concetti
from buddy.config import SOGLIA_RADAR

from .radar import tutte_le_sessioni

DOMANDE_DEMO = {
    "analisi1": [
        "Compute the limit as x → 0 of (2x − sin 2x) / x³",
        "Compute the limit as x → 0 of (1 − cos 4x) / x²",
        "Study the convergence of the series with general term 1/n²",
        "Compute the limit as x → 0 of (tan x − sin x) / x³",
    ],
    "fisica1": [
        "A ball is thrown upward at 15 m/s: after how long is it back to the ground?",
        "A body is dropped from rest from 45 m: how fast does it hit the ground?",
        "Compute the moment of inertia of a uniform disc about its axis",
    ],
    "informatica": [
        "What does this program print: for i in range(2, 8): print(i)",
        "How many iterations does it run: i = 0; while i < 9: i = i + 2",
        "Write a recursive function that computes the factorial of n",
    ],
}

SOGLIA_ATTENZIONE = 40  # % di errori scoperti da soli sotto cui segnaliamo


def _trova_concetti(domanda: str) -> list[str]:
    testo = domanda.lower()
    trovati = []
    for cid, c in concetti().items():
        for chiave in c["parole_chiave"]:
            chiave = chiave.strip().lower()
            if chiave.endswith("*"):  # prefisso: lanciat* trova "lanciata"
                schema = rf"\b{re.escape(chiave[:-1])}"
            elif chiave.isalnum():
                schema = rf"\b{re.escape(chiave)}\b"
            else:
                schema = re.escape(chiave)
            if re.search(schema, testo):
                trovati.append(cid)
                break
    return trovati


def analizza(domande: list[str]) -> list[dict]:
    sessioni = tutte_le_sessioni()
    tutti = concetti()
    report = []
    for i, domanda in enumerate(d.strip() for d in domande if d.strip()):
        cids = _trova_concetti(domanda)
        voce = {"numero": i + 1, "domanda": domanda, "concetti": [tutti[c]["nome"] for c in cids]}
        if not cids:
            voce.update(stato="nessun_dato",
                        testo="No sessions on this topic: we do not know how prepared the class is.")
            report.append(voce)
            continue

        dettagli = []
        peggiore = None
        for cid in cids:
            mie = [s for s in sessioni if cid in s["concetti"]]
            con_errore = [s for s in mie if s["tentativi"] > 0]
            if len(mie) < SOGLIA_RADAR or not con_errore:
                dettagli.append(f"{tutti[cid]['nome']}: only {len(mie)} sessions, not enough data")
                peggiore = peggiore if peggiore is not None else -1
                continue
            pct = round(100 * sum(s["esito"] == "da_solo" for s in con_errore) / len(con_errore))
            dettagli.append(
                f"{tutti[cid]['nome']}: in {len(con_errore)} sessions with a mistake, found alone in {pct}% of cases"
            )
            peggiore = pct if peggiore in (None, -1) else min(peggiore, pct)

        if peggiore == -1:
            stato = "insufficiente"
            consiglio = "Not enough data to give an indication."
        elif peggiore < SOGLIA_ATTENZIONE:
            stato = "attenzione"
            consiglio = "Consider a targeted practice session before the exam, or keep the difficulty if it is intended."
        else:
            stato = "ok"
            consiglio = "In line with the preparation shown in the sessions."
        voce.update(stato=stato, testo="; ".join(dettagli) + ". " + consiglio)
        report.append(voce)
    return report
