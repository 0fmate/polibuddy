"""Esegue il piano dello studente con strumenti affidabili (SymPy, mpmath, simulatori nostri).

I numeri mostrati allo studente sono calcolati qui, mai inventati dal modello.
Tre motori: limite (sostituzioni + tabella vicino a 0), valore (cosa succede con il valore
proposto), traccia (programma eseguito passo per passo dal nostro simulatore).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import mpmath as mp
import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from .catalogo import Esercizio, simboli, x
from .config import PRECISIONE_CIFRE, PUNTI_TABELLA

_TRASFORMAZIONI = standard_transformations + (implicit_multiplication_application, convert_xor)
_FUNZIONI = {"e": sp.E, "E": sp.E, "pi": sp.pi, "sen": sp.sin, "tg": sp.tan, "ln": sp.log, "oo": sp.oo,
             "sqrt": sp.sqrt, "ceil": sp.ceiling, "ceiling": sp.ceiling, "floor": sp.floor}
_O_PICCOLO = re.compile(r"[+-]?\s*\b[oO]\s*\([^()]*(\([^()]*\))*[^()]*\)")


def leggi(testo: str, valori: dict | None = None) -> sp.Expr:
    """Legge un'espressione scritta dal modello o dalle regole offline.

    I termini "o piccolo" (o(x^3)) vengono tolti: sono un resto, non un pezzo da calcolare.
    """
    pulito = (
        testo.replace("·", "*").replace("−", "-").replace("²", "**2").replace("³", "**3")
        .replace("√", "sqrt").replace("₀", "0").replace("infinity", "oo").replace("infinito", "oo").replace(",", ".").strip()
    )
    pulito = _O_PICCOLO.sub("", pulito).strip() or "0"
    valori = valori or {}
    loc = {**simboli(valori), **_FUNZIONI}
    e = parse_expr(pulito, local_dict=loc, transformations=_TRASFORMAZIONI)
    return e.subs({sp.Symbol(k): sp.nsimplify(v) for k, v in valori.items()})


def fmt_num(v: float | None, cifre: int = 6) -> str:
    """Number for display (English: decimal point)."""
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "—"
    return f"{v:.{cifre}g}"


def fmt_valore(espr: sp.Expr | None, cifre: int = 4) -> str:
    if espr is None:
        return "—"
    if espr == sp.oo:
        return "infinity"
    if espr == -sp.oo:
        return "minus infinity"
    try:
        return fmt_num(float(espr), cifre)
    except (TypeError, ValueError):
        return str(espr)


def _valuta(espr: sp.Expr, var: sp.Symbol, punti: list[str]) -> list[float | None]:
    mp.mp.dps = PRECISIONE_CIFRE
    fn = sp.lambdify(var, espr, "mpmath")
    risultati: list[float | None] = []
    for p in punti:
        try:
            v = float(fn(mp.mpf(p)))
            risultati.append(v if math.isfinite(v) else None)
        except (ZeroDivisionError, ValueError, TypeError, OverflowError):
            risultati.append(None)
    return risultati


def _curva(espr: sp.Expr, var: sp.Symbol, da: float, a: float, n: int = 120, salta_zero: bool = False):
    passo = (a - da) / n
    xs = [round(da + i * passo, 6) for i in range(n + 1)]
    if salta_zero:
        xs = [v for v in xs if abs(v) > 1e-9]
    ys = _valuta(espr, var, [repr(v) for v in xs])
    return [[xv, (yv if yv is not None and abs(yv) < 1e6 else None)] for xv, yv in zip(xs, ys)]


@dataclass
class Esecuzione:
    colonne: list[str]
    righe: list[list[str]]
    etichetta_previsto: str
    previsto: str
    etichetta_tendenza: str
    tendenza: str
    torna: bool
    grafico: dict
    evidenzia: int | None = None
    valori_reali: list[float | None] = field(default_factory=list)  # per le battute del compagno
    non_applicate: list[str] = field(default_factory=list)

    def pubblico(self) -> dict:
        return {
            "colonne": self.colonne,
            "righe": self.righe,
            "evidenzia": self.evidenzia,
            "etichetta_previsto": self.etichetta_previsto,
            "previsto": self.previsto,
            "etichetta_tendenza": self.etichetta_tendenza,
            "tendenza": self.tendenza,
            "torna": self.torna,
            "grafico": self.grafico,
        }


def applica_sostituzioni(f: sp.Expr, sostituzioni: list[tuple[sp.Expr, sp.Expr]]) -> tuple[sp.Expr, list[str]]:
    g = f
    non_applicate: list[str] = []
    for da, verso in sostituzioni:
        nuovo = g.subs(da, verso)
        if nuovo == g:
            non_applicate.append(str(da))
        g = nuovo
    return g, non_applicate


# ---------------------------------------------------------------- motore: limite

def _esegui_limite(es: Esercizio, sostituzioni, previsto_testo: str) -> Esecuzione:
    g: sp.Expr | None = None
    non_applicate: list[str] = []
    if sostituzioni:
        g, non_applicate = applica_sostituzioni(es.f, sostituzioni)
        g = sp.simplify(g)

    previsto: sp.Expr | None = None
    if g is not None:
        previsto = sp.limit(g, x, 0)
    elif previsto_testo.strip():
        try:
            previsto = leggi(previsto_testo, es.valori)
        except (sp.SympifyError, SyntaxError, TypeError):
            previsto = None

    reali = _valuta(es.f, x, PUNTI_TABELLA)
    tuoi = _valuta(g, x, PUNTI_TABELLA) if g is not None else [None] * len(PUNTI_TABELLA)
    righe = [[fmt_num(float(p)), fmt_num(r, 9), fmt_num(t, 9)] for p, r, t in zip(PUNTI_TABELLA, reali, tuoi)]

    limite_vero = sp.limit(es.f, x, 0)  # resta nel server: non viene mai mostrato come risultato
    torna = previsto is not None and sp.simplify(previsto - limite_vero) == 0
    ultimo = next((v for v in reversed(reali) if v is not None), None)
    tendenza = fmt_num(ultimo, 3)

    linee = []
    serie = [{"punti": _curva(es.f, x, -0.6, 0.6, salta_zero=True), "ruolo": "vero", "etichetta": "true function"}]
    if g is not None:
        serie.append({"punti": _curva(g, x, -0.6, 0.6, salta_zero=True), "ruolo": "tuo", "etichetta": "your plan"})
    elif previsto is not None and previsto.is_finite:
        linee.append({"y": float(previsto), "ruolo": "tuo", "etichetta": "your plan"})
    grafico = {
        "x_min": -0.6, "x_max": 0.6, "asse_x": "x", "serie": serie, "linee": linee,
        "marcatore": {"x": 0, "y": ultimo, "testo": f"→ {tendenza}", "ruolo": "vero"} if ultimo is not None else None,
    }
    return Esecuzione(
        colonne=["x", "true value", "your plan"],
        righe=righe,
        etichetta_previsto="your plan predicts",
        previsto=fmt_valore(previsto),
        etichetta_tendenza="the numbers approach",
        tendenza=tendenza,
        torna=bool(torna),
        grafico=grafico,
        valori_reali=reali,
        non_applicate=non_applicate,
    )


# ---------------------------------------------------------------- motore: valore

def _con_unita(v: float, unita: str) -> str:
    if abs(v) < 1e-6:  # residui numerici (5e-15 m) mostrati come zero
        v = 0.0
    return f"{fmt_num(v, 3)} {unita}".strip()


def _esegui_valore(es: Esercizio, valore: sp.Expr | None) -> Esecuzione:
    c = es.cfg
    var = sp.Symbol(c["variabile"])
    osservabile = leggi(c["osservabile"], es.valori)
    obiettivo = float(leggi(c["obiettivo"], es.valori))
    vero = float(es.vero)
    V = float(valore) if valore is not None and valore.is_real is not False else None
    if V is None or not math.isfinite(V) or V <= 0:
        V = None

    punti = [V * k for k in (0.25, 0.5, 0.75, 1.0)] if V else []
    oss = _valuta(osservabile, var, [repr(p) for p in punti]) if punti else []
    oss = [0.0 if o is not None and abs(o) < 1e-6 else o for o in oss]
    righe = [[fmt_num(p, 3), fmt_num(o, 3), c.get("nota_riga", "") if i == len(punti) - 1 else ""]
             for i, (p, o) in enumerate(zip(punti, oss))]
    oss_v = oss[-1] if oss else None
    torna = V is not None and abs(V - vero) <= 0.03 * abs(vero)

    fine = max(1.25 * (V or 0), 1.12 * vero)
    marcatore = None
    if V is not None and oss_v is not None:
        marcatore = {"x": V, "y": oss_v, "testo": c.get("nota_riga", "").replace("← ", ""), "ruolo": "tuo"}
    grafico = {
        "x_min": 0, "x_max": fine, "asse_x": c.get("asse_x", ""),
        "serie": [{"punti": _curva(osservabile, var, 0, fine), "ruolo": "vero", "etichetta": c.get("etichetta_curva", "")}],
        "linee": [{"y": obiettivo, "ruolo": "obiettivo", "etichetta": c.get("etichetta_obiettivo", "")}],
        "marcatore": marcatore,
    }
    return Esecuzione(
        colonne=c["colonne"],
        righe=righe,
        evidenzia=len(righe) - 1 if righe else None,
        etichetta_previsto=c["etichetta_previsto"],
        previsto=_con_unita(V, c.get("unita", "")) if V is not None else "—",
        etichetta_tendenza=c["etichetta_tendenza"],
        tendenza=_con_unita(oss_v, c.get("unita_osservabile", "")) if oss_v is not None else "—",
        torna=torna,
        grafico=grafico,
        valori_reali=oss,
    )


# ---------------------------------------------------------------- motore: traccia

def _somma_range(n: int) -> tuple[list[list], int]:
    righe, s = [], 0
    for passo, i in enumerate(range(1, n), start=1):
        s = s + i
        righe.append([passo, i, s])
    return righe, s


def _conta_while(n: int) -> tuple[list[list], int]:
    righe, i, conta = [], 0, 0
    while i < n:
        conta = conta + 1
        righe.append([conta, i, conta])
        i = i + 2
    return righe, conta


SIMULATORI = {"somma_range": _somma_range, "conta_while": _conta_while}


def _esegui_traccia(es: Esercizio, valore: sp.Expr | None) -> Esecuzione:
    c = es.cfg
    righe_num, finale = SIMULATORI[c["simulatore"]](int(es.valori["n"]))
    V = None
    if valore is not None:
        try:
            V = float(valore)
        except (TypeError, ValueError):
            V = None
    torna = V is not None and abs(V - finale) < 1e-9
    linee = [{"y": V, "ruolo": "tuo", "etichetta": "your value"}] if V is not None else []
    grafico = {
        "x_min": 0, "x_max": len(righe_num) + 0.5, "asse_x": c.get("asse_x", ""), "linee": linee,
        "serie": [{"punti": [[0, 0]] + [[r[0], r[2]] for r in righe_num], "ruolo": "vero",
                   "etichetta": c.get("etichetta_curva", ""), "punti_visibili": True}],
        "marcatore": {"x": righe_num[-1][0], "y": finale, "testo": f"→ {finale}", "ruolo": "vero"} if righe_num else None,
    }
    return Esecuzione(
        colonne=c["colonne"],
        righe=[[str(v) for v in r] for r in righe_num],
        evidenzia=len(righe_num) - 1 if righe_num else None,
        etichetta_previsto=c["etichetta_previsto"],
        previsto=fmt_num(V) if V is not None else "—",
        etichetta_tendenza=c["etichetta_tendenza"],
        tendenza=str(finale),
        torna=torna,
        grafico=grafico,
        valori_reali=[float(r[2]) for r in righe_num],
    )


def esegui(es: Esercizio, sostituzioni=None, previsto_testo: str = "", valore: sp.Expr | None = None) -> Esecuzione:
    if es.motore == "valore":
        return _esegui_valore(es, valore)
    if es.motore == "traccia":
        return _esegui_traccia(es, valore)
    return _esegui_limite(es, sostituzioni or [], previsto_testo)
