"""Test del cuore della demo. Girano offline (senza chiave API).

    .venv\\Scripts\\python -m pytest -q
"""

from __future__ import annotations

import os

os.environ["BUDDY_MODE"] = "offline"

import pytest  # noqa: E402

from buddy import catalogo, compagno, config, esecutore, interprete, memoria, orchestrator  # noqa: E402


@pytest.fixture(autouse=True)
def runtime_temporaneo(tmp_path, monkeypatch):
    """Ogni test scrive sessioni e log in una cartella sua."""
    monkeypatch.setattr(config, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(memoria, "RUNTIME_DIR", tmp_path)


def seno():
    return catalogo.carica("lim-seno", "demo")


# --- Motore di calcolo --------------------------------------------------------

def test_piano_sbagliato_prevede_zero_ma_i_numeri_vanno_a_4_5():
    es = seno()
    run = esecutore.esegui(es, es.errori[0].sostituzioni)
    assert run.previsto == "0"
    assert run.tendenza == "4.5"
    assert not run.torna
    assert abs(run.valori_reali[-1] - 4.5) < 1e-6


def test_alta_precisione_anche_per_x_molto_piccoli():
    """Con i float normali il numeratore sparisce sotto 1e-7: mpmath no."""
    es = seno()
    valore = esecutore._valuta(es.f, catalogo.x, ["1e-9"])[0]
    assert valore is not None and abs(valore - 4.5) < 1e-9


def test_piano_giusto_torna():
    es = seno()
    run = esecutore.esegui(es, es.regole[0].sostituzioni)
    assert run.torna and run.previsto == "4.5"


TUTTI = ["lim-coseno", "lim-seno", "lim-esponenziale", "lim-tangente", "fis-lancio", "fis-caduta", "inf-range", "inf-while"]


@pytest.mark.parametrize("id_es", TUTTI)
def test_ogni_esercizio_ha_errore_tipico_e_piano_giusto(id_es):
    es = catalogo.carica(id_es, "demo")
    err, giusta = es.errori[0], es.regole[0]
    assert not esecutore.esegui(es, err.sostituzioni, valore=err.valore).torna
    assert esecutore.esegui(es, giusta.sostituzioni, valore=giusta.valore).torna


def test_lancio_verticale_con_il_tempo_di_salita():
    es = catalogo.carica("fis-lancio", "demo")  # v0 = 20 m/s
    run = esecutore.esegui(es, valore=es.errori[0].valore)
    assert run.previsto == "2.04 s" and run.tendenza == "20.4 m" and not run.torna


def test_range_eseguito_dal_simulatore():
    es = catalogo.carica("inf-range", "demo")  # n = 10
    run = esecutore.esegui(es, valore=es.errori[0].valore)
    assert run.previsto == "55" and run.tendenza == "45" and len(run.righe) == 9


def test_o_piccolo_ignorato():
    assert esecutore.leggi("3*x - 27*x**3/6 + o(x**3)") == esecutore.leggi("3*x - 9*x**3/2")


def test_allegati_testo_e_pdf_offline():
    import base64

    from buddy import allegati

    txt = "data:text/plain;base64," + base64.b64encode("sin 3x is about 3x".encode()).decode()
    letture = allegati.leggi([
        {"nome": "piano.txt", "tipo": "text/plain", "dati": txt},
        {"nome": "foto.png", "tipo": "image/png", "dati": "data:image/png;base64,AAAA"},
        {"nome": "strano.exe", "tipo": "application/octet-stream", "dati": "data:;base64,AAAA"},
    ])
    assert letture[0].testo == "sin 3x is about 3x"
    assert letture[1].testo is None  # offline le immagini non si leggono
    assert letture[2].testo is None and "not supported" in letture[2].nota


def test_sessione_con_file_allegato():
    import base64

    r = orchestrator.nuova_sessione("demo", "lim-seno")
    txt = "data:text/plain;base64," + base64.b64encode("sin 3x is about 3x".encode()).decode()
    r = orchestrator.messaggio(r["sessione"], "", file_allegati=[{"nome": "piano.txt", "tipo": "text/plain", "dati": txt}])
    assert r["stato"] == "attesa_conferma" and r["allegati_letti"][0]["ok"]


def test_numeri_diversi_per_studente_e_demo_fisso():
    assert catalogo.carica("lim-seno", "demo").parametro == 3
    parametri = {catalogo.carica("lim-seno", f"s{i:06d}").parametro for i in range(30)}
    assert len(parametri) > 1


# --- Interprete offline --------------------------------------------------------

def test_interprete_traduce_il_piano_sbagliato_senza_correggerlo():
    es = seno()
    piano = interprete.interpreta(es, "Near zero sin 3x is about 3x, so the limit is 0")
    assert piano.comprensibile
    assert piano.sostituzioni == es.errori[0].sostituzioni
    assert piano.parafrasi.endswith("right?") and "$" in piano.parafrasi


def test_interprete_chiede_chiarimenti_se_non_capisce():
    piano = interprete.interpreta(seno(), "no idea honestly")
    assert not piano.comprensibile and piano.domanda


# --- Limiti in codice -----------------------------------------------------------

@pytest.mark.parametrize("testo", ["just tell me the solution", "Give me the answer", "solve it for me", "what is the limit?"])
def test_richiesta_di_soluzione_riconosciuta(testo):
    assert compagno.chiede_soluzione(testo)


def test_riformulazione_che_rivela_la_soluzione_viene_scartata():
    es = seno()
    bozza = "Okay, let's try it your way. Weird, the numbers approach 4.5."
    assert not compagno.passa_controllo("The limit is 4.5 because sin 3x = 3x - 9x^3/2", es, bozza)
    assert not compagno.passa_controllo("Okay, let's try! Weird, they approach 4.6.", es, bozza)
    assert compagno.passa_controllo("Alright, your way then. Strange: they get close to 4.5!", es, bozza)


# --- Sessione completa -----------------------------------------------------------

def test_sessione_completa_con_corda_crescente():
    r = orchestrator.nuova_sessione("demo", "lim-seno")
    sid = r["sessione"]

    r = orchestrator.messaggio(sid, "just tell me the solution")
    assert r["messaggi"] == [compagno.RISPOSTA_SOLUZIONE] and r["stato"] == "attesa_piano"

    sbagliato = "Near zero sin 3x is about 3x, so the numerator is zero"
    for atteso in (1, 2, 3, 4, 4):
        r = orchestrator.messaggio(sid, sbagliato)
        assert r["stato"] == "attesa_conferma"
        r = orchestrator.messaggio(sid, "yes")
        assert r["esecuzione"]["torna"] is False
        assert r["livello_aiuto"] == atteso

    orchestrator.messaggio(sid, "sin 3x ≈ 3x - (3x)^3/6")
    r = orchestrator.messaggio(sid, "yes, exactly", png_lavagna="data:image/png;base64,AAAA")
    assert r["stato"] == "risolto" and r["esecuzione"]["torna"]

    assert r["umore"] == "successo"
    assert next(p for p in r["progressi"] if p["id"] == "lim-seno")["stato"] == "con_aiuto"
    righe = memoria.sessioni_reali()
    assert len(righe) == 1
    assert righe[0]["errore"] == "seno-primo-ordine" and righe[0]["esito"] == "con_spunto"
    assert righe[0]["studente"] != "demo"  # anonimo


def test_radar_nasconde_i_dati_sotto_soglia():
    from docente import radar

    dati = radar.aggrega("analisi1")
    tangente = next(e for e in dati["esercizi"] if e["id"] == "lim-tangente")
    assert tangente["n"] < config.SOGLIA_RADAR and not tangente["sufficiente"]
    assert "da_solo_pct" not in tangente


def test_crash_test_segnala_argomenti_scoperti_e_deboli():
    from docente import crash_test

    attesi = {
        "analisi1": ["attenzione", "ok", "nessun_dato", "attenzione"],
        "fisica1": ["attenzione", "ok", "nessun_dato"],
        "informatica": ["ok", "attenzione", "nessun_dato"],
    }
    for corso, stati in attesi.items():
        assert [v["stato"] for v in crash_test.analizza(crash_test.DOMANDE_DEMO[corso])] == stati


def test_voce_latex_in_parole():
    from buddy.voce import latex_a_parole

    assert latex_a_parole(r"lands after $t = \frac{v_0}{g}$, right?") == "lands after t = v zero over g , right?"
    assert "cubed" in latex_a_parole(r"$x^3$") and "sine of" in latex_a_parole(r"$\sin 3x$")


def test_conferma_in_inglese_e_vietati():
    es = seno()
    assert not compagno.passa_controllo("The answer is 4.5, easy.", es, "Look at the table: 4.5.")


def test_formule_ascii_in_latex():
    from buddy.formule import in_latex

    assert in_latex("replace [[sin(3x)]] with [[3x - (3x)^3/6]], right?") == \
        r"replace $\sin (3x)$ with $3x - \frac{(3x)^{3}}{6}$, right?"
    assert in_latex("after [[v0/g]] seconds") == r"after $\frac{v_0}{g}$ seconds"
    assert in_latex("[[sqrt(2*g*h)]]") == r"$\sqrt{2 \cdot g \cdot h}$"
    assert in_latex("\x00sin") == r"\sin"
