"""Caricamento del catalogo e scelta degli esercizi personalizzati."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from functools import lru_cache

import sympy as sp
import yaml

from .config import CATALOGO_PATH

x = sp.Symbol("x")


def coeff_x(valore) -> str:
    """'3x', oppure 'x' se il coefficiente è 1."""
    return "x" if valore == 1 else f"{valore}x"


def _fmt(v) -> str:
    return str(v).replace(".", ",") if isinstance(v, float) else str(v)


def riempi(testo: str, valori: dict) -> str:
    if "a" in valori:
        testo = testo.replace("{ax}", coeff_x(valori["a"]))
    for nome, v in valori.items():
        testo = testo.replace("{" + nome + "}", _fmt(v))
    return testo


def simboli(valori: dict) -> dict:
    """Simboli SymPy per parametri, costanti e variabili."""
    loc = {nome: sp.Symbol(nome) for nome in valori}
    loc.update({"x": x, "t": sp.Symbol("t"), "v": sp.Symbol("v")})
    return loc


def espressione(testo: str, valori: dict) -> sp.Expr:
    loc = simboli(valori)
    e = sp.sympify(testo, locals=loc)
    return e.subs({loc[k]: sp.nsimplify(v) for k, v in valori.items()})


@dataclass
class Errore:
    id: str
    nome: str
    sostituzioni: list[tuple[sp.Expr, sp.Expr]]
    valore: sp.Expr | None
    domanda_mirata: str
    spunto: str


@dataclass
class Regola:
    tutte: list[str]
    almeno_una: list[str]
    richiede_una: list[str]
    sostituzioni: list[tuple[sp.Expr, sp.Expr]]
    valore: sp.Expr | None
    parafrasi: str


@dataclass
class Esercizio:
    id: str
    corso: str
    motore: str  # limite | valore | traccia
    titolo: str
    tipo: str
    livello: int
    concetti: list[str]
    valori: dict  # parametri dello studente + costanti
    testo: str
    latex: str
    codice: str
    slide: str
    piano_demo: str
    f: sp.Expr | None = None  # funzione del limite (motore limite)
    vero: sp.Expr | None = None  # risposta corretta (motori valore e traccia): resta nel server
    cfg: dict = field(default_factory=dict)  # etichette, frasi, osservabile... già riempiti
    errori: list[Errore] = field(default_factory=list)
    regole: list[Regola] = field(default_factory=list)
    vietato: list[str] = field(default_factory=list)

    @property
    def parametro(self):
        """Primo parametro (compatibilità: per i limiti è `a`)."""
        return next(iter(self.valori.values()))

    def pubblico(self) -> dict:
        """Quello che il browser può vedere: niente soluzione, niente errori tipici."""
        return {
            "id": self.id,
            "corso": self.corso,
            "corso_nome": corsi()[self.corso]["nome"],
            "motore": self.motore,
            "titolo": self.titolo,
            "tipo": self.tipo,
            "livello": self.livello,
            "latex": self.latex,
            "testo": self.testo,
            "codice": self.codice,
            "piano_demo": self.piano_demo,
        }


@lru_cache(maxsize=1)
def _grezzo() -> dict:
    return yaml.safe_load(CATALOGO_PATH.read_text(encoding="utf-8"))


def corsi() -> dict[str, dict]:
    return _grezzo()["corsi"]


def concetti() -> dict[str, dict]:
    return _grezzo()["concetti"]


def esercizi_grezzi(corso: str | None = None) -> list[dict]:
    tutti = [e for e in _grezzo()["esercizi"] if corso in (None, e["corso"])]
    ordine = list(corsi())
    return sorted(tutti, key=lambda e: (ordine.index(e["corso"]), e["livello"]))


def valori_per(studente: str, grezzo: dict) -> dict:
    """Numeri diversi per ogni studente; lo studente 'demo' ha quelli della demo."""
    if studente.strip().lower() == "demo":
        scelti = dict(grezzo["demo"])
    else:
        scelti = {}
        for nome, opzioni in grezzo["parametri"].items():
            h = int(hashlib.sha256(f"{studente}:{grezzo['id']}:{nome}".encode()).hexdigest(), 16)
            scelti[nome] = opzioni[h % len(opzioni)]
    return {**scelti, **grezzo.get("costanti", {})}


def _sost(lista: list[dict], valori: dict) -> list[tuple[sp.Expr, sp.Expr]]:
    return [(espressione(s["da"], valori), espressione(s["a"], valori)) for s in lista]


_CHIAVI_TESTO = [
    "colonne", "nota_riga", "etichetta_previsto", "etichetta_tendenza", "asse_x", "etichetta_curva",
    "etichetta_obiettivo", "frase_contraddizione", "frase_ancora", "frase_torna", "unita", "unita_osservabile",
    "variabile", "osservabile", "obiettivo", "simulatore",
]


def carica(id_esercizio: str, studente: str) -> Esercizio:
    g = next(e for e in esercizi_grezzi() if e["id"] == id_esercizio)
    tutti = valori_per(studente, g)
    # nei testi si sostituiscono solo i parametri: le costanti (g) comparirebbero dentro il LaTeX (\frac{v_0}{g})
    val = {k: v for k, v in tutti.items() if k not in g.get("costanti", {})}
    cfg = {}
    for chiave in _CHIAVI_TESTO:
        if chiave in g:
            cfg[chiave] = [riempi(c, val) for c in g[chiave]] if isinstance(g[chiave], list) else riempi(str(g[chiave]), val)

    def valore_opz(d: dict) -> sp.Expr | None:
        return espressione(d["valore"], tutti) if "valore" in d else None

    return Esercizio(
        id=g["id"],
        corso=g["corso"],
        motore=g.get("motore", "limite"),
        titolo=g["titolo"],
        tipo=g["tipo"],
        livello=int(g["livello"]),
        concetti=list(g["concetti"]),
        valori=tutti,
        testo=riempi(g["testo"], val),
        latex=riempi(g.get("latex", ""), val),
        codice=riempi(g.get("codice", ""), val),
        slide=g["slide"],
        piano_demo=riempi(g.get("piano_demo", ""), val),
        f=espressione(g["espressione"], tutti) if "espressione" in g else None,
        vero=espressione(g["vero"], tutti) if "vero" in g else None,
        cfg=cfg,
        errori=[
            Errore(
                id=e["id"],
                nome=e["nome"],
                sostituzioni=_sost(e.get("sostituzioni", []), tutti),
                valore=valore_opz(e),
                domanda_mirata=riempi(e["domanda_mirata"], val),
                spunto=riempi(e["spunto"], val),
            )
            for e in g.get("errori", [])
        ],
        regole=[
            Regola(
                tutte=[riempi(t, val) for t in r.get("tutte", [])],
                almeno_una=[riempi(t, val) for t in r.get("almeno_una", [])],
                richiede_una=[riempi(t, val) for t in r.get("richiede_una", [])],
                sostituzioni=_sost(r.get("sostituzioni", []), tutti),
                valore=valore_opz(r),
                parafrasi=riempi(r["parafrasi"], val),
            )
            for r in g.get("regole_offline", [])
        ],
        vietato=[riempi(v, val) for v in g.get("vietato", [])],
    )
