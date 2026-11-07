"""Radar per il docente: dati anonimi e aggregati, sopra una soglia minima.

Per la demo le sessioni vere si sommano a un set di sessioni SIMULATE (dichiarato in pagina).
"""

from __future__ import annotations

from collections import Counter

from buddy.catalogo import corsi, esercizi_grezzi
from buddy.config import SOGLIA_RADAR
from buddy.memoria import ESITI, sessioni_reali

# Profili simulati: (sessioni, risolte al primo tentativo, ripartizione degli esiti di chi ha sbagliato).
_PROFILI_SIMULATI = {
    "lim-coseno": (46, 16, {"da_solo": 0.60, "dopo_domanda": 0.25, "dopo_slide": 0.08, "con_spunto": 0.04, "non_risolto": 0.03}),
    "lim-seno": (120, 18, {"da_solo": 0.30, "dopo_domanda": 0.32, "dopo_slide": 0.18, "con_spunto": 0.12, "non_risolto": 0.08}),
    "lim-esponenziale": (64, 14, {"da_solo": 0.45, "dopo_domanda": 0.30, "dopo_slide": 0.12, "con_spunto": 0.08, "non_risolto": 0.05}),
    "lim-tangente": (8, 1, {"da_solo": 0.25, "dopo_domanda": 0.25, "dopo_slide": 0.25, "con_spunto": 0.125, "non_risolto": 0.125}),
    "fis-lancio": (84, 12, {"da_solo": 0.25, "dopo_domanda": 0.35, "dopo_slide": 0.2, "con_spunto": 0.12, "non_risolto": 0.08}),
    "fis-caduta": (52, 15, {"da_solo": 0.5, "dopo_domanda": 0.3, "dopo_slide": 0.1, "con_spunto": 0.06, "non_risolto": 0.04}),
    "inf-range": (140, 30, {"da_solo": 0.55, "dopo_domanda": 0.3, "dopo_slide": 0.08, "con_spunto": 0.05, "non_risolto": 0.02}),
    "inf-while": (63, 10, {"da_solo": 0.35, "dopo_domanda": 0.33, "dopo_slide": 0.17, "con_spunto": 0.1, "non_risolto": 0.05}),
}


def dati_simulati() -> list[dict]:
    righe: list[dict] = []
    for grezzo in esercizi_grezzi():
        profilo = _PROFILI_SIMULATI.get(grezzo["id"])
        if not profilo:
            continue
        n, primo_colpo, ripartizione = profilo
        errore = grezzo["errori"][0]["id"] if grezzo.get("errori") else None
        base = {"esercizio": grezzo["id"], "tipo": grezzo["tipo"], "concetti": grezzo["concetti"], "simulata": True}
        righe += [{**base, "errore": None, "tentativi": 0, "esito": "da_solo"} for _ in range(primo_colpo)]
        con_errore = n - primo_colpo
        conteggi = {k: round(v * con_errore) for k, v in ripartizione.items()}
        conteggi["da_solo"] += con_errore - sum(conteggi.values())  # arrotondamenti
        for esito, c in conteggi.items():
            righe += [{**base, "errore": errore, "tentativi": 1 + ESITI.index(esito), "esito": esito} for _ in range(c)]
    return righe


def tutte_le_sessioni() -> list[dict]:
    return dati_simulati() + sessioni_reali()


def _pct(parte: int, totale: int) -> int:
    return round(100 * parte / totale) if totale else 0


def aggrega(corso: str = "analisi1") -> dict:
    corso = corso if corso in corsi() else "analisi1"
    ids = {e["id"] for e in esercizi_grezzi(corso)}
    sessioni = [s for s in tutte_le_sessioni() if s["esercizio"] in ids]
    nomi_errori = {e["id"]: e["nome"] for g in esercizi_grezzi() for e in g.get("errori", [])}
    righe = []
    for grezzo in esercizi_grezzi(corso):
        mie = [s for s in sessioni if s["esercizio"] == grezzo["id"]]
        n = len(mie)
        riga = {
            "id": grezzo["id"],
            "titolo": grezzo["titolo"],
            "tipo": grezzo["tipo"],
            "livello": grezzo["livello"],
            "n": n,
            "sufficiente": n >= SOGLIA_RADAR,
        }
        if riga["sufficiente"]:
            con_errore = [s for s in mie if s["tentativi"] > 0]
            esiti = Counter(s["esito"] for s in con_errore)
            errore = Counter(s["errore"] for s in con_errore if s["errore"]).most_common(1)
            riga.update({
                "primo_colpo_pct": _pct(n - len(con_errore), n),
                "n_con_errore": len(con_errore),
                "esiti_pct": {e: _pct(esiti.get(e, 0), len(con_errore)) for e in ESITI},
                "da_solo_pct": _pct(esiti.get("da_solo", 0), len(con_errore)),
                "errore_principale": nomi_errori.get(errore[0][0], "") if errore else "",
            })
        righe.append(riga)

    valide = [r for r in righe if r["sufficiente"]]
    n_tot = len(sessioni)
    con_errore_tot = sum(r["n_con_errore"] for r in valide)
    da_solo_tot = sum(round(r["da_solo_pct"] * r["n_con_errore"] / 100) for r in valide)
    primo_tot = sum(round(r["primo_colpo_pct"] * r["n"] / 100) for r in valide)
    lacune = sorted(valide, key=lambda r: r["da_solo_pct"])[:2]
    critico = lacune[0] if lacune else None
    return {
        "corso": corso,
        "corso_nome": corsi()[corso]["nome"],
        "corsi": [{"id": k, "nome": v["nome"]} for k, v in corsi().items()],
        "critico": {"titolo": critico["titolo"], "da_solo_pct": critico["da_solo_pct"]} if critico else None,
        "soglia": SOGLIA_RADAR,
        "sessioni_totali": n_tot,
        "sessioni_reali": sum(1 for s in sessioni if not s.get("simulata")),
        "primo_colpo_pct": _pct(primo_tot, sum(r["n"] for r in valide)),
        "da_solo_pct": _pct(da_solo_tot, con_errore_tot),
        "esercizi": righe,
        "lacune": [
            {"titolo": r["titolo"], "errore": r["errore_principale"], "da_solo_pct": r["da_solo_pct"], "n": r["n_con_errore"]}
            for r in lacune
        ],
        "esiti": ESITI,
    }
