"""The student's plan in structured form.

The model only produces this object: the maths is done by code (engine.py),
so a wrong plan is never silently "corrected".
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubstitutionModel(BaseModel):
    from_expr: str = Field(description="SymPy expression that appears in the exercise, e.g. sin(3*x)")
    to_expr: str = Field(description="SymPy expression the student replaces it with, e.g. 3*x")


class Plan(BaseModel):
    understandable: bool = Field(description="False if this is not a plan for this exercise")
    clarifying_question: str = Field(description="Short English question if the plan is unclear, otherwise empty string")
    substitutions: list[SubstitutionModel] = Field(description="The student's approximations, even if wrong")
    predicted_limit: str = Field(description="Value the student says they get (SymPy: 0, 9/2, oo), or empty string")
    proposed_value: str = Field(
        description="Exercises with an answer (physics, programs): formula or number proposed by the student, "
        "in SymPy syntax with the exercise symbols (e.g. v0/g, sqrt(g*h), n*(n+1)/2, 45); otherwise empty string"
    )
    paraphrase: str = Field(
        description="The plan restated in the second person, formulas as ASCII maths between [[ ]], ending with 'right?'"
    )
