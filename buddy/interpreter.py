"""Understands the student's plan and translates it, without correcting it.

With a model configured it uses structured outputs; without one, the catalog rules do the job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp

from . import llm
from .catalog import Exercise, Substitution
from .engine import fmt_num, fmt_value, parse
from .formulas import to_latex
from .plan import Plan

SYSTEM_PROMPT = r"""You are the interpreter of PoliBuddy, a study buddy for first-year engineering students.
You receive an exercise and the student's plan, possibly written loosely (sometimes with text read
from a whiteboard, a photo or a voice transcript). The student usually writes in English.

Your job is to TRANSLATE the plan faithfully into a structured form, NOT to correct it.
If the student uses a wrong approximation, a wrong formula or a wrong value, report it exactly as it is:
the code will run it and the student will see for themselves that it does not work.

Field rules:
- LIMIT exercises: put every approximation of the student in "substitutions". "from_expr" is a piece that
  appears literally in the SymPy expression of the exercise (e.g. sin(3*x)); "to_expr" is what the student
  replaces it with (e.g. 3*x). Do not include little-o terms (o(x^3)). Leave "proposed_value" empty.
- Exercises with an ANSWER (physics, programs): "proposed_value" is the formula or number the student
  proposes as the answer, in SymPy syntax with the given symbols (e.g. v0/g, sqrt(g*h), n*(n+1)/2, 45).
  Leave "substitutions" empty.
- predicted_limit: the value the student says they get for a limit (0, 9/2, oo), or an empty string.
- paraphrase: one English sentence, second person, that restates the plan in your own words, without
  judging it and without hints, ending with "right?". Write EVERY formula in plain ASCII maths between
  double square brackets, e.g. [[sin(3x)]], [[3x - (3x)^3/6]], [[x^3]], [[v0/g]], [[sqrt(2*g*h)]].
  Never use backslashes or LaTeX commands.
- If the text is not a plan for this exercise (or asks for the solution), understandable=false and
  clarifying_question holds a short English question to understand how they want to proceed
  (formulas again between [[ ]]).
Never add steps the student did not say."""

_NUMBER_AFTER_VERB = re.compile(
    r"(?:is|equals|gives|get|=|result|prints|after|about|around|approximately|runs|loops)\s*"
    r"(-?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?|zero|infinity)"
)
_NUMBER_WITH_UNIT = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*(?:s\b|sec|seconds|m/s|meters per second|metres per second|times)")


@dataclass
class Interpretation:
    understandable: bool
    substitutions: list[Substitution] = field(default_factory=list)
    predicted_limit: str = ""
    value: sp.Expr | None = None
    paraphrase: str = ""
    question: str = ""
    source: str = "rules"  # rules | model


def normalize(text: str) -> str:
    """Lower case, no spaces, no LaTeX markup: what the offline rules compare against."""
    t = text.lower()
    for old, new in (("²", "^2"), ("³", "^3"), ("−", "-"), ("·", "*"), ("**", "^"), ("₀", "0"),
                     ("\\cdot", "*"), ("\\approx", "≈"), ("\\", ""), ("{", ""), ("}", ""), ("$", ""),
                     ("e^(", "e^"), ("’", "'")):
        t = t.replace(old, new)
    return re.sub(r"\s+", "", t)


def format_value(ex: Exercise, value: sp.Expr) -> str:
    if ex.engine == "value":
        return f"{fmt_num(float(value), 3)} {ex.cfg.get('unit', '')}".strip()
    return fmt_value(value, 6)


def _number_in_text(text: str, with_unit: bool) -> str:
    t = text.lower()
    if with_unit:
        found = _NUMBER_WITH_UNIT.findall(t)
        if found:
            return found[-1].replace(",", ".")
    found = _NUMBER_AFTER_VERB.findall(t)
    if not found:
        return ""
    v = found[-1].replace(" ", "")
    return {"zero": "0", "infinity": "oo"}.get(v, v.replace(",", "."))


def _offline(ex: Exercise, text: str) -> Interpretation:
    n = normalize(text)
    for r in ex.rules:
        if not all(normalize(t) in n for t in r.all):
            continue
        if r.requires_any and not any(normalize(t) in n for t in r.requires_any):
            continue
        if r.any and not any(normalize(t) in n for t in r.any):
            continue
        paraphrase = r.paraphrase
        if r.value is not None:
            paraphrase = paraphrase.replace("{value}", format_value(ex, r.value))
        return Interpretation(True, r.substitutions, "", r.value, paraphrase, source="rules")

    number = _number_in_text(text, with_unit=ex.engine == "value")
    if number:
        try:
            v = parse(number, ex.values)
            if ex.engine == "limit":
                return Interpretation(True, [], number, None, f"So you say the limit is ${fmt_value(v)}$, right?")
            return Interpretation(True, [], "", v, f"So you say the answer is {format_value(ex, v)}, right?")
        except (sp.SympifyError, SyntaxError, TypeError):
            pass
    example = r'"$\sin 3x$ is about $3x$"' if ex.engine == "limit" else '"I think it is …, because …"'
    return Interpretation(
        False, question=f"I'm not sure I got your plan. Can you explain it in your own words? For example: {example}."
    )


def _describe(ex: Exercise) -> str:
    if ex.engine == "limit":
        return f"LIMIT exercise: {ex.text}\nSymPy expression: limit as x -> 0 of {sp.sstr(ex.f)}"
    syms = ", ".join(f"{k} = {v}" for k, v in ex.values.items())
    code = f"\nCode:\n{ex.code}" if ex.code else ""
    return f"Exercise with an ANSWER: {ex.text}{code}\nAvailable symbols: {syms}"


def _from_model(ex: Exercise, text: str) -> Interpretation | None:
    plan = llm.structured(SYSTEM_PROMPT, f"{_describe(ex)}\n\nStudent's plan:\n{text}", Plan)
    if plan is None:
        return None
    paraphrase = to_latex(plan.paraphrase)
    question = to_latex(plan.clarifying_question)
    if not plan.understandable:
        return Interpretation(False, question=question or "How would you like to proceed?", source="model")
    try:
        subs = [(parse(s.from_expr, ex.values), parse(s.to_expr, ex.values)) for s in plan.substitutions]
        value = parse(plan.proposed_value, ex.values) if plan.proposed_value.strip() else None
    except (sp.SympifyError, SyntaxError, TypeError):
        return Interpretation(False, question="I can't quite translate your idea. Can you rewrite it?", source="model")
    if ex.engine != "limit" and value is None:
        return Interpretation(False, question="What is your answer, even an approximate one?", source="model")
    return Interpretation(True, subs, plan.predicted_limit, value, paraphrase, source="model")


def interpret(ex: Exercise, text: str, extra_text: str = "") -> Interpretation:
    """`extra_text`: text read from the whiteboard, attachments or voice, added to the plan."""
    full = text.strip()
    if extra_text.strip():
        full = f"{full}\n{extra_text.strip()}".strip()
    result = _from_model(ex, full) if llm.available() else None
    return result or _offline(ex, full)
