"""Il piano dello studente in forma strutturata.

Il modello produce solo questo oggetto: il calcolo lo fa il codice (esecutore.py),
così un piano sbagliato non viene "corretto" di nascosto.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Sostituzione(BaseModel):
    da: str = Field(description="SymPy expression that appears in the exercise, e.g. sin(3*x)")
    a: str = Field(description="SymPy expression the student replaces it with, e.g. 3*x")


class Piano(BaseModel):
    comprensibile: bool = Field(description="False if this is not a plan for this exercise")
    domanda_chiarimento: str = Field(description="Short English question if the plan is unclear, otherwise empty string")
    sostituzioni: list[Sostituzione] = Field(description="The student's approximations, even if wrong")
    limite_previsto: str = Field(description="Value the student says they get (SymPy: 0, 9/2, oo), or empty string")
    valore_proposto: str = Field(
        description="Exercises with an answer (physics, programs): formula or number proposed by the student, "
        "in SymPy syntax with the exercise symbols (e.g. v0/g, sqrt(g*h), n*(n+1)/2, 45); otherwise empty string"
    )
    parafrasi: str = Field(description="The plan restated in the second person, formulas in LaTeX between $...$, ending with 'right?'")
