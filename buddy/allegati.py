"""Foto e documenti caricati dallo studente nella chat.

- immagini: le legge il modello multimodale (senza modello non si possono leggere);
- PDF: testo estratto con pypdf (funziona anche offline, non per i PDF scansionati);
- file di testo e codice: letti direttamente.
Il contenuto letto viene aggiunto al piano e ripetuto allo studente prima di eseguire.
"""

from __future__ import annotations

import base64
import binascii
import io
from dataclasses import dataclass

from . import llm

MAX_BYTE = 8 * 1024 * 1024
MAX_CARATTERI = 4000
_TESTO = (".txt", ".md", ".py", ".csv", ".json", ".c", ".java", ".m", ".tex")

SYSTEM_FOTO = r"""A student uploaded a photo or image (notes, a worked exercise, code, formulas).
Transcribe the relevant content faithfully: text, formulas in LaTeX between $...$ (e.g. $\sin 3x \approx 3x$, $x^3$),
code. Do not correct mistakes, do not complete steps, do not add comments.
If the image contains nothing readable, reply only: EMPTY"""


@dataclass
class Lettura:
    nome: str
    testo: str | None
    nota: str

    def pubblico(self) -> dict:
        sintesi = (self.testo or "")[:220] + ("…" if self.testo and len(self.testo) > 220 else "")
        return {"nome": self.nome, "ok": self.testo is not None, "sintesi": sintesi, "nota": self.nota}


def _decodifica(dati: str) -> bytes | None:
    try:
        grezzo = dati.split(",", 1)[1] if dati.startswith("data:") else dati
        return base64.b64decode(grezzo, validate=False)
    except (binascii.Error, ValueError, IndexError):
        return None


def _leggi_immagine(nome: str, dati: str) -> Lettura:
    if not llm.disponibile():
        return Lettura(nome, None, "without the model I cannot read images: please type your plan")
    letto = llm.testo(SYSTEM_FOTO, [llm.immagine_png(dati), {"type": "text", "text": "Transcribe the content."}],
                      max_tokens=1500)
    if not letto or letto.strip().upper().startswith("EMPTY"):
        return Lettura(nome, None, "I could not read anything in this image")
    return Lettura(nome, letto.strip()[:MAX_CARATTERI], "read by the model")


def _leggi_pdf(nome: str, contenuto: bytes) -> Lettura:
    try:
        from pypdf import PdfReader

        lettore = PdfReader(io.BytesIO(contenuto))
        testo = "\n".join((p.extract_text() or "") for p in lettore.pages[:5]).strip()
    except Exception:  # PDF danneggiato o cifrato
        return Lettura(nome, None, "I cannot open this PDF")
    if not testo:
        return Lettura(nome, None, "PDF without selectable text (a scan): upload a photo of the page instead")
    return Lettura(nome, testo[:MAX_CARATTERI], "text extracted from the PDF")


def leggi(allegati: list[dict]) -> list[Lettura]:
    letture: list[Lettura] = []
    for a in allegati[:5]:
        nome = str(a.get("nome", "file"))[:80]
        tipo = str(a.get("tipo", ""))
        dati = str(a.get("dati", ""))
        contenuto = _decodifica(dati)
        if contenuto is None:
            letture.append(Lettura(nome, None, "unreadable file"))
        elif len(contenuto) > MAX_BYTE:
            letture.append(Lettura(nome, None, "file too large (8 MB max)"))
        elif tipo.startswith("image/"):
            letture.append(_leggi_immagine(nome, dati))
        elif tipo == "application/pdf" or nome.lower().endswith(".pdf"):
            letture.append(_leggi_pdf(nome, contenuto))
        elif tipo.startswith("text/") or nome.lower().endswith(_TESTO):
            testo = contenuto.decode("utf-8", errors="replace").strip()
            letture.append(Lettura(nome, testo[:MAX_CARATTERI] or None, "text file"))
        else:
            letture.append(Lettura(nome, None, "file type not supported (use images, PDF or text)"))
    return letture


def come_testo(letture: list[Lettura]) -> str:
    return "\n".join(f"(Content of {l.nome}: {l.testo})" for l in letture if l.testo)
