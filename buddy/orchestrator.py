"""La sessione dello studente come macchina a stati.

Il codice decide le fasi (piano → conferma → esecuzione → commento) e quanta corda dare;
il modello capisce il piano e dà voce al compagno, ma non decide mai quando si è finito.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

import sympy as sp

from . import allegati, compagno, interprete, lavagna, memoria
from .catalogo import Errore, Esercizio, carica, corsi, esercizi_grezzi
from .config import LIVELLO_AIUTO_MAX
from .esecutore import applica_sostituzioni, esegui

_SI = re.compile(r"^\s*(yes|yeah|yep|yup|right|correct|exactly|ok|okay|sure|confirm|that'?s right|s[iì]|esatto)\b", re.I)
_NO = re.compile(r"^\s*(no|nope|not|wrong|wait|hold on)\b", re.I)

# Stati della mascotte (file in web/brand/mascotte/)
UMORE_DOPO_ERRORE = {1: "riflessione", 2: "riprova", 3: "riprova", 4: "idea"}


@dataclass
class Sessione:
    id: str
    studente: str
    esercizio: Esercizio
    stato: str = "attesa_piano"  # attesa_piano | attesa_conferma | risolto
    tentativi: int = 0
    livello_aiuto: int = 0
    in_attesa: interprete.Interpretazione | None = None
    errore: Errore | None = None
    registrata: bool = False
    fonte: str = "regole"
    umore: str = "default"
    messaggi: list[dict] = field(default_factory=list)


SESSIONI: dict[str, Sessione] = {}


def _ids(corso: str | None) -> list[str]:
    return [e["id"] for e in esercizi_grezzi(corso)]


def scegli_esercizio(studente: str, preferito: str | None = None, corso: str | None = None) -> str:
    if preferito in _ids(None):
        return preferito
    corso = corso if corso in corsi() else "analisi1"
    ids = _ids(corso)
    risolti = set(memoria.profilo(studente)["risolti"])
    # difficoltà dinamica: il primo esercizio non ancora risolto, in ordine di livello
    return next((i for i in ids if i not in risolti), ids[-1])


def progressi(studente: str, corso: str) -> list[dict]:
    p = memoria.profilo(studente)
    return [
        {"id": e["id"], "titolo": e["titolo"], "livello": e["livello"], "stato": memoria.stato_argomento(p, e["id"])}
        for e in esercizi_grezzi(corso)
    ]


def _risposta(s: Sessione, testi: list[str], esecuzione=None, lavagna_letta: str | None = None,
              letture: list | None = None) -> dict:
    for t in testi:
        s.messaggi.append({"ruolo": "buddy", "testo": t})
    return {
        "sessione": s.id,
        "esercizio": s.esercizio.pubblico(),
        "messaggi": testi,
        "stato": s.stato,
        "umore": s.umore,
        "tentativi": s.tentativi,
        "livello_aiuto": s.livello_aiuto,
        "livello_aiuto_max": LIVELLO_AIUTO_MAX,
        "esecuzione": esecuzione.pubblico() if esecuzione else None,
        "lavagna_letta": lavagna_letta,
        "allegati_letti": [l.pubblico() for l in (letture or [])],
        "progressi": progressi(s.studente, s.esercizio.corso),
        "fonte": s.fonte,
    }


def nuova_sessione(studente: str, esercizio: str | None = None, corso: str | None = None) -> dict:
    studente = studente.strip() or "demo"
    es = carica(scegli_esercizio(studente, esercizio, corso), studente)
    s = Sessione(id=uuid.uuid4().hex[:12], studente=studente, esercizio=es)
    SESSIONI[s.id] = s
    memoria.log_passo(s.id, "inizio", {"esercizio": es.id, "valori": es.valori})
    return _risposta(s, [compagno.benvenuto(es)])


def _uguali(a: sp.Expr | None, b: sp.Expr | None) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return sp.simplify(a - b) == 0


def _riconosci_errore(es: Esercizio, piano: interprete.Interpretazione) -> Errore | None:
    """L'errore tipico del catalogo che corrisponde al piano dello studente."""
    for err in es.errori:
        if err.valore is not None:
            if _uguali(piano.valore, err.valore):
                return err
            continue
        if len(err.sostituzioni) != len(piano.sostituzioni):
            continue
        if all(
            any(sp.simplify(d1 - d2) == 0 and sp.simplify(a1 - a2) == 0 for d2, a2 in piano.sostituzioni)
            for d1, a1 in err.sostituzioni
        ):
            return err
    return None


def _registra(s: Sessione, esito: str) -> None:
    if s.registrata:
        return
    memoria.registra_sessione(
        s.studente, s.esercizio.id, s.esercizio.tipo, s.esercizio.concetti,
        s.errore.id if s.errore else None, s.tentativi, esito,
    )
    s.registrata = True


def _esegui_piano(s: Sessione) -> dict:
    piano = s.in_attesa
    assert piano is not None
    run = esegui(s.esercizio, piano.sostituzioni, piano.limite_previsto, piano.valore)
    memoria.log_passo(s.id, "esecuzione", {"previsto": run.previsto, "torna": run.torna, "tendenza": run.tendenza})
    s.in_attesa = None

    if run.torna:
        bozza = compagno.dopo_esecuzione(s.esercizio, run, s.livello_aiuto, s.tentativi, s.errore)
        s.stato = "risolto"
        s.umore = "successo"
        esito = memoria.esito_da_livello(s.livello_aiuto)
        _registra(s, esito)
        memoria.segna_risolto(s.studente, s.esercizio.id, esito)
    else:
        s.tentativi += 1
        s.livello_aiuto = min(s.tentativi, LIVELLO_AIUTO_MAX)
        riconosciuto = _riconosci_errore(s.esercizio, piano)
        s.errore = s.errore or riconosciuto
        bozza = compagno.dopo_esecuzione(s.esercizio, run, s.livello_aiuto, s.tentativi, riconosciuto)
        s.stato = "attesa_piano"
        s.umore = UMORE_DOPO_ERRORE[s.livello_aiuto]
        memoria.segna_tentato(s.studente, s.esercizio.id)
    return _risposta(s, [compagno.riformula(bozza, s.esercizio)], esecuzione=run)


def messaggio(id_sessione: str, testo: str = "", png_lavagna: str | None = None,
              file_allegati: list[dict] | None = None) -> dict:
    s = SESSIONI[id_sessione]
    testo = (testo or "").strip()
    file_allegati = file_allegati or []
    s.messaggi.append({"ruolo": "studente", "testo": testo})
    memoria.log_passo(s.id, "messaggio", {
        "testo": testo, "lavagna": bool(png_lavagna), "allegati": [a.get("nome") for a in file_allegati], "stato": s.stato,
    })

    # Limite in codice: la soluzione non si chiede, la si costruisce.
    if testo and compagno.chiede_soluzione(testo):
        memoria.log_passo(s.id, "limite_rispettato", {"testo": testo})
        s.umore = "default"
        return _risposta(s, [compagno.RISPOSTA_SOLUZIONE])

    # Una conferma ("sì" / "no") vale anche se il browser allega la lavagna.
    if s.stato == "attesa_conferma" and testo and not file_allegati:
        if _SI.match(testo):
            return _esegui_piano(s)
        if _NO.match(testo) and len(testo) < 25:
            s.in_attesa = None
            s.stato = "attesa_piano"
            s.umore = "riflessione"
            return _risposta(s, [compagno.rispiega()])
        # altrimenti lo trattiamo come un piano nuovo

    letto = lavagna.leggi(png_lavagna) if png_lavagna else None
    letture = allegati.leggi(file_allegati) if file_allegati else []
    testo_letto = "\n".join(filter(None, [
        f"(Written on the whiteboard: {letto})" if letto else "",
        allegati.come_testo(letture),
    ]))

    if not testo and not testo_letto:
        if letture or png_lavagna:
            note = "; ".join(f"{l.nome}: {l.nota}" for l in letture) if letture else \
                "I cannot read the whiteboard (no model, or it is empty)"
            return _risposta(s, [f"I cannot use what you sent me ({note}). "
                                 "Please type your plan below as well."], lavagna_letta=letto, letture=letture)
        return _risposta(s, ["Tell me your plan: how would you solve it?"])

    piano = interprete.interpreta(s.esercizio, testo, testo_letto)
    s.fonte = piano.fonte
    memoria.log_passo(s.id, "interpretazione", {
        "fonte": piano.fonte, "comprensibile": piano.comprensibile, "valore": str(piano.valore),
        "sostituzioni": [f"{d} -> {v}" for d, v in piano.sostituzioni], "previsto": piano.limite_previsto,
    })
    if not piano.comprensibile:
        s.umore = "riflessione"
        return _risposta(s, [piano.domanda], lavagna_letta=letto, letture=letture)

    if piano.sostituzioni and s.esercizio.f is not None:
        _, non_applicate = applica_sostituzioni(s.esercizio.f, piano.sostituzioni)
        if non_applicate and len(non_applicate) == len(piano.sostituzioni):
            s.umore = "riflessione"
            return _risposta(s, [compagno.sostituzione_assente(non_applicate[0])], lavagna_letta=letto, letture=letture)

    s.in_attesa = piano
    s.stato = "attesa_conferma"
    s.umore = "studio"
    return _risposta(s, [piano.parafrasi], lavagna_letta=letto, letture=letture)


def prossimo(id_sessione: str) -> dict:
    s = SESSIONI[id_sessione]
    if s.stato != "risolto" and s.tentativi > 0:
        _registra(s, "non_risolto")
    ids = _ids(s.esercizio.corso)
    risolti = set(memoria.profilo(s.studente)["risolti"])
    i = ids.index(s.esercizio.id)
    dopo = ids[i + 1:] + ids[: i + 1]
    seguente = next((e for e in dopo if e not in risolti), dopo[0])
    return nuova_sessione(s.studente, seguente)
