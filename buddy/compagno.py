"""PoliBuddy's lines and the in-code safety checks.

Every line starts from a draft written here (reliable). If the model is available, the draft is
rephrased more naturally, but the rephrasing must pass a check: if it reveals the solution or
changes the numbers, it is discarded and the draft is used.
Formulas are written in LaTeX between $...$ and rendered by the browser.
"""

from __future__ import annotations

import os
import re

from . import llm
from .catalogo import Errore, Esercizio
from .config import REASONING_EFFORT_COMPAGNO
from .esecutore import Esecuzione, fmt_num

RIFORMULA = os.environ.get("BUDDY_RIFORMULA", "1") != "0"

_CHIEDE_SOLUZIONE = re.compile(
    r"(tell\s+me|give\s+me|show\s+me|what'?s|what\s+is|just\s+tell)\b.{0,30}(solution|answer|result|limit)"
    r"|solve\s+it\s+(for\s+me|yourself)|you\s+do\s+it|just\s+give\s+me|i\s+don'?t\s+know,?\s+tell\s+me"
    r"|dimmi\b.{0,30}soluzion|dammi\b.{0,30}(soluzion|risultat|rispost)",
    re.IGNORECASE,
)

RISPOSTA_SOLUZIONE = (
    "Let's try your idea first: how would you solve it? "
    "It's fine if you're not sure, I'll do the maths."
)

_VIETATI_GENERALI = [
    "the limit is", "the limit equals", "the answer is", "the solution is", "the result is",
    "correct answer", "correct procedure", "the right answer",
]

SYSTEM_COMPAGNO = """You are PoliBuddy: a study buddy for a first-year engineering student, not a professor.
You receive a DRAFT of your next line and rephrase it naturally.

Rules:
- English, at most 3 short sentences, friendly peer tone.
- Keep EXACTLY all the numbers of the draft, written the same way.
- Keep every formula in LaTeX between $...$, exactly as in the draft.
- Do not add information, formulas, hints or steps that are not in the draft.
- Never state the solution and never reveal the correct method:
  you may only describe what the numbers in the table show.
- Reply with the line only, no quotes."""

_FRASI_LIMITE = {
    "frase_contraddizione": "If you were right, as we get close to zero we should see numbers close to {previsto}. "
                            "Instead, look: {primi}… they approach {tendenza}.",
    "frase_ancora": "your plan gives {previsto}, but the numbers approach {tendenza}.",
    "frase_torna": "your plan gives {previsto}, and the numbers really approach {tendenza}.",
}


def chiede_soluzione(testo: str) -> bool:
    return bool(_CHIEDE_SOLUZIONE.search(testo))


def passa_controllo(battuta: str, es: Esercizio, bozza: str) -> bool:
    """True if the rephrased line is safe to show."""
    bassa = battuta.lower()
    if any(v in bassa for v in _VIETATI_GENERALI):
        return False
    if any(v.lower() in bassa for v in es.vietato if v.lower() not in bozza.lower()):
        return False
    numeri_bozza = set(re.findall(r"\d+(?:\.\d+)?", bozza))
    numeri_battuta = set(re.findall(r"\d+(?:\.\d+)?", battuta))
    # every number of the draft must stay, and no new ones may appear
    return numeri_bozza == numeri_battuta


def riformula(bozza: str, es: Esercizio) -> str:
    if not (RIFORMULA and llm.disponibile()):
        return bozza
    for _ in range(2):
        proposta = llm.testo(SYSTEM_COMPAGNO, f"Draft: {bozza}", max_tokens=1500, effort=REASONING_EFFORT_COMPAGNO)
        if proposta and passa_controllo(proposta, es, bozza):
            return proposta
    return bozza


# --- Drafts ------------------------------------------------------------------

def benvenuto(es: Esercizio) -> str:
    dove = "the code above" if es.codice else "the exercise above"
    return (
        f"Hi! Let's try this one: {es.testo} (see {dove}). How would you solve it? "
        "Tell me your plan, even roughly: you can use the whiteboard, attach a photo of your sheet or just talk to me."
    )


def rispiega() -> str:
    return "Okay, then explain it again: what do you want to do, step by step?"


def sostituzione_assente(da: str) -> str:
    return f"I tried to follow your plan, but ${da}$ does not appear in the exercise. Can you rewrite it?"


def _frase(es: Esercizio, chiave: str, run: Esecuzione) -> str:
    modello = es.cfg.get(chiave) or _FRASI_LIMITE[chiave]
    primi = ", ".join(fmt_num(v, 5) for v in run.valori_reali[:3] if v is not None)
    return modello.replace("{previsto}", run.previsto).replace("{tendenza}", run.tendenza).replace("{primi}", primi)


def dopo_esecuzione(
    es: Esercizio, run: Esecuzione, livello_aiuto: int, tentativi: int, errore: Errore | None = None
) -> str:
    if run.torna:
        dettaglio = _frase(es, "frase_torna", run)
        if tentativi == 0:
            return f"It works on the first try: {dettaglio} Want to try a harder one?"
        return f"It works! {dettaglio[0].upper()}{dettaglio[1:]} You found the mistake yourself. Want to try another one?"

    if run.previsto == "—":
        osservazione = (
            "I tried your plan, but it doesn't lead to a precise value. "
            f"Meanwhile, look at the table: {run.etichetta_tendenza} {run.tendenza}."
        )
    elif livello_aiuto <= 1:
        return f"Okay, let's try it your way. {_frase(es, 'frase_contraddizione', run)} Weird, where did we lose it?"
    else:
        osservazione = f"Still not right: {_frase(es, 'frase_ancora', run)}"

    if livello_aiuto <= 1:
        return f"{osservazione} Where do you think the problem is?"
    if livello_aiuto == 2:
        domanda = errore.domanda_mirata if errore else "Which step of your plan convinces you the least?"
        return f"{osservazione} {domanda}"
    if livello_aiuto == 3:
        return f"{osservazione} I suggest rereading this: {es.slide}. Then try again with your own idea."
    spunto = (errore.spunto if errore else None) or (es.errori[0].spunto if es.errori else "Start again from the definition.")
    return f"{osservazione} A hint: {spunto} The rest is up to you."
