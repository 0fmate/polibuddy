"""Understands the student's plan and translates it, without correcting it.

With an API key the OpenAI model does it (structured outputs); without one, the catalogue rules do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp

from . import llm
from .catalogo import Esercizio
from .esecutore import fmt_num, fmt_valore, leggi
from .formule import in_latex
from .piano import Piano

SYSTEM_INTERPRETE = r"""You are the interpreter of PoliBuddy, a study buddy for first-year engineering students.
You receive an exercise and the student's plan, possibly written loosely (sometimes with text read
from a whiteboard, a photo or a voice transcript). The student usually writes in English.

Your job is to TRANSLATE the plan faithfully into a structured form, NOT to correct it.
If the student uses a wrong approximation, a wrong formula or a wrong value, report it exactly as it is:
the code will run it and the student will see for themselves that it does not work.

Field rules:
- LIMIT exercises: put every approximation of the student in "sostituzioni". "da" is a piece that appears
  literally in the SymPy expression of the exercise (e.g. sin(3*x)); "a" is what the student replaces it
  with (e.g. 3*x). Do not include little-o terms (o(x^3)). Leave "valore_proposto" empty.
- Exercises with an ANSWER (physics, programs): "valore_proposto" is the formula or number the student
  proposes as the answer, in SymPy syntax with the given symbols (e.g. v0/g, sqrt(g*h), n*(n+1)/2, 45).
  Leave "sostituzioni" empty.
- limite_previsto: the value the student says they get for a limit (0, 9/2, oo), or an empty string.
- parafrasi: one English sentence, second person, that restates the plan in your own words, without
  judging it and without hints, ending with "right?". Write EVERY formula in plain ASCII maths between
  double square brackets, e.g. [[sin(3x)]], [[3x - (3x)^3/6]], [[x^3]], [[v0/g]], [[sqrt(2*g*h)]].
  Never use backslashes or LaTeX commands.
- If the text is not a plan for this exercise (or asks for the solution), comprensibile=false and
  domanda_chiarimento holds a short English question to understand how they want to proceed
  (formulas again between [[ ]]).
Never add steps the student did not say."""

_RIF_NUMERO = re.compile(
    r"(?:is|equals|gives|get|=|result|prints|after|about|around|approximately|runs|loops)\s*"
    r"(-?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?|zero|infinity)"
)
_NUMERO_CON_UNITA = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*(?:s\b|sec|seconds|m/s|meters per second|metres per second|times)")


@dataclass
class Interpretazione:
    comprensibile: bool
    sostituzioni: list[tuple[sp.Expr, sp.Expr]] = field(default_factory=list)
    limite_previsto: str = ""
    valore: sp.Expr | None = None
    parafrasi: str = ""
    domanda: str = ""
    fonte: str = "regole"


def normalizza(testo: str) -> str:
    """Lower case, no spaces, no LaTeX markup: what the offline rules compare against."""
    t = testo.lower()
    for vecchio, nuovo in (("²", "^2"), ("³", "^3"), ("−", "-"), ("·", "*"), ("**", "^"), ("₀", "0"),
                           ("\\cdot", "*"), ("\\approx", "≈"), ("\\", ""), ("{", ""), ("}", ""), ("$", ""),
                           ("e^(", "e^"), ("’", "'")):
        t = t.replace(vecchio, nuovo)
    return re.sub(r"\s+", "", t)


def formato_valore(es: Esercizio, valore: sp.Expr) -> str:
    if es.motore == "valore":
        return f"{fmt_num(float(valore), 3)} {es.cfg.get('unita', '')}".strip()
    return fmt_valore(valore, 6)


def _numero_dal_testo(testo: str, con_unita: bool) -> str:
    t = testo.lower()
    if con_unita:
        trovati = _NUMERO_CON_UNITA.findall(t)
        if trovati:
            return trovati[-1].replace(",", ".")
    trovati = _RIF_NUMERO.findall(t)
    if not trovati:
        return ""
    v = trovati[-1].replace(" ", "")
    return {"zero": "0", "infinity": "oo"}.get(v, v.replace(",", "."))


def _offline(es: Esercizio, testo: str) -> Interpretazione:
    n = normalizza(testo)
    for r in es.regole:
        if not all(normalizza(t) in n for t in r.tutte):
            continue
        if r.richiede_una and not any(normalizza(t) in n for t in r.richiede_una):
            continue
        if r.almeno_una and not any(normalizza(t) in n for t in r.almeno_una):
            continue
        parafrasi = r.parafrasi
        if r.valore is not None:
            parafrasi = parafrasi.replace("{valore}", formato_valore(es, r.valore))
        return Interpretazione(True, r.sostituzioni, "", r.valore, parafrasi, fonte="regole")

    numero = _numero_dal_testo(testo, con_unita=es.motore == "valore")
    if numero:
        try:
            v = leggi(numero, es.valori)
            if es.motore == "limite":
                return Interpretazione(True, [], numero, None,
                                       f"So you say the limit is ${fmt_valore(v)}$, right?", fonte="regole")
            return Interpretazione(True, [], "", v,
                                   f"So you say the answer is {formato_valore(es, v)}, right?", fonte="regole")
        except (sp.SympifyError, SyntaxError, TypeError):
            pass
    esempio = r'"$\sin 3x$ is about $3x$"' if es.motore == "limite" else '"I think it is …, because …"'
    return Interpretazione(
        False,
        domanda=f"I'm not sure I got your plan. Can you explain it in your own words? For example: {esempio}.",
        fonte="regole",
    )


def _descrizione(es: Esercizio) -> str:
    if es.motore == "limite":
        return f"LIMIT exercise: {es.testo}\nSymPy expression: limit as x -> 0 of {sp.sstr(es.f)}"
    simboli = ", ".join(f"{k} = {v}" for k, v in es.valori.items())
    codice = f"\nCode:\n{es.codice}" if es.codice else ""
    return f"Exercise with an ANSWER: {es.testo}{codice}\nAvailable symbols: {simboli}"


def _da_modello(es: Esercizio, testo: str) -> Interpretazione | None:
    messaggio = f"{_descrizione(es)}\n\nStudent's plan:\n{testo}"
    piano = llm.strutturato(SYSTEM_INTERPRETE, messaggio, Piano)
    if piano is None:
        return None
    piano.parafrasi = in_latex(piano.parafrasi)
    piano.domanda_chiarimento = in_latex(piano.domanda_chiarimento)
    if not piano.comprensibile:
        return Interpretazione(False, domanda=piano.domanda_chiarimento or "How would you like to proceed?",
                               fonte="modello")
    try:
        sost = [(leggi(s.da, es.valori), leggi(s.a, es.valori)) for s in piano.sostituzioni]
        valore = leggi(piano.valore_proposto, es.valori) if piano.valore_proposto.strip() else None
    except (sp.SympifyError, SyntaxError, TypeError):
        return Interpretazione(False, domanda="I can't quite translate your idea. Can you rewrite it?", fonte="modello")
    if es.motore != "limite" and valore is None:
        return Interpretazione(False, domanda="What is your answer, even an approximate one?", fonte="modello")
    return Interpretazione(True, sost, piano.limite_previsto, valore, piano.parafrasi, fonte="modello")


def interpreta(es: Esercizio, testo: str, letture: str = "") -> Interpretazione:
    """`letture`: text read from the whiteboard, attachments or voice, added to the plan."""
    completo = testo.strip()
    if letture.strip():
        completo = f"{completo}\n{letture.strip()}".strip()
    risultato = _da_modello(es, completo) if llm.disponibile() else None
    return risultato or _offline(es, completo)
