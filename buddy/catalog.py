"""Loads the catalog and builds exercises personalised for each student."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from functools import lru_cache

import sympy as sp
import yaml

from .config import CATALOG_PATH

x = sp.Symbol("x")


def coeff_x(value) -> str:
    """'3x', or 'x' when the coefficient is 1."""
    return "x" if value == 1 else f"{value}x"


def fill(text: str, values: dict) -> str:
    """Replaces {param} placeholders (and {ax}) with the student's values."""
    if "a" in values:
        text = text.replace("{ax}", coeff_x(values["a"]))
    for name, v in values.items():
        text = text.replace("{" + name + "}", str(v))
    return text


def symbols(values: dict) -> dict:
    """SymPy symbols for parameters, constants and variables."""
    loc = {name: sp.Symbol(name) for name in values}
    loc.update({"x": x, "t": sp.Symbol("t"), "v": sp.Symbol("v")})
    return loc


def expression(text: str, values: dict) -> sp.Expr:
    loc = symbols(values)
    e = sp.sympify(text, locals=loc)
    return e.subs({loc[k]: sp.nsimplify(v) for k, v in values.items()})


Substitution = tuple[sp.Expr, sp.Expr]


@dataclass
class Mistake:
    id: str
    name: str
    substitutions: list[Substitution]
    value: sp.Expr | None
    targeted_question: str
    hint: str


@dataclass
class OfflineRule:
    all: list[str]
    any: list[str]
    requires_any: list[str]
    substitutions: list[Substitution]
    value: sp.Expr | None
    paraphrase: str


@dataclass
class Exercise:
    id: str
    course: str
    engine: str  # limit | value | trace
    title: str
    topic: str
    level: int
    concepts: list[str]
    values: dict  # the student's parameters + constants
    text: str
    latex: str
    code: str
    slide: str
    demo_plan: str
    f: sp.Expr | None = None  # function of the limit (limit engine)
    answer: sp.Expr | None = None  # correct answer (value and trace engines): stays on the server
    cfg: dict = field(default_factory=dict)  # labels, lines, observable... already filled
    mistakes: list[Mistake] = field(default_factory=list)
    rules: list[OfflineRule] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)

    @property
    def param(self):
        """First parameter (for the limits it is `a`)."""
        return next(iter(self.values.values()))

    def public(self) -> dict:
        """What the browser may see: no solution, no typical mistakes."""
        return {
            "id": self.id,
            "course": self.course,
            "course_name": courses()[self.course]["name"],
            "engine": self.engine,
            "title": self.title,
            "topic": self.topic,
            "level": self.level,
            "latex": self.latex,
            "text": self.text,
            "code": self.code,
            "demo_plan": self.demo_plan,
        }


@lru_cache(maxsize=1)
def _raw() -> dict:
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))


def courses() -> dict[str, dict]:
    return _raw()["courses"]


def concepts() -> dict[str, dict]:
    return _raw()["concepts"]


def raw_exercises(course: str | None = None) -> list[dict]:
    selected = [e for e in _raw()["exercises"] if course in (None, e["course"])]
    order = list(courses())
    return sorted(selected, key=lambda e: (order.index(e["course"]), e["level"]))


def values_for(student: str, raw: dict) -> dict:
    """Different numbers for every student; the student 'demo' gets the demo numbers."""
    if student.strip().lower() == "demo":
        chosen = dict(raw["demo"])
    else:
        chosen = {}
        for name, options in raw["params"].items():
            h = int(hashlib.sha256(f"{student}:{raw['id']}:{name}".encode()).hexdigest(), 16)
            chosen[name] = options[h % len(options)]
    return {**chosen, **raw.get("constants", {})}


def _substitutions(items: list[dict], values: dict) -> list[Substitution]:
    return [(expression(s["from"], values), expression(s["to"], values)) for s in items]


_TEXT_KEYS = [
    "columns", "row_note", "predicted_label", "observed_label", "x_label", "curve_label", "target_label",
    "contradiction_line", "still_wrong_line", "works_line", "unit", "observable_unit",
    "variable", "observable", "target", "simulator",
]


def load(exercise_id: str, student: str) -> Exercise:
    raw = next(e for e in raw_exercises() if e["id"] == exercise_id)
    values = values_for(student, raw)
    # texts only get the parameters: constants (g) would end up inside the LaTeX (\frac{v_0}{g})
    params = {k: v for k, v in values.items() if k not in raw.get("constants", {})}
    cfg = {}
    for key in _TEXT_KEYS:
        if key in raw:
            cfg[key] = [fill(c, params) for c in raw[key]] if isinstance(raw[key], list) else fill(str(raw[key]), params)

    def optional_value(d: dict) -> sp.Expr | None:
        return expression(d["value"], values) if "value" in d else None

    return Exercise(
        id=raw["id"],
        course=raw["course"],
        engine=raw.get("engine", "limit"),
        title=raw["title"],
        topic=raw["topic"],
        level=int(raw["level"]),
        concepts=list(raw["concepts"]),
        values=values,
        text=fill(raw["text"], params),
        latex=fill(raw.get("latex", ""), params),
        code=fill(raw.get("code", ""), params),
        slide=raw["slide"],
        demo_plan=fill(raw.get("demo_plan", ""), params),
        f=expression(raw["expression"], values) if "expression" in raw else None,
        answer=expression(raw["answer"], values) if "answer" in raw else None,
        cfg=cfg,
        mistakes=[
            Mistake(
                id=m["id"],
                name=m["name"],
                substitutions=_substitutions(m.get("substitutions", []), values),
                value=optional_value(m),
                targeted_question=fill(m["targeted_question"], params),
                hint=fill(m["hint"], params),
            )
            for m in raw.get("mistakes", [])
        ],
        rules=[
            OfflineRule(
                all=[fill(t, params) for t in r.get("all", [])],
                any=[fill(t, params) for t in r.get("any", [])],
                requires_any=[fill(t, params) for t in r.get("requires_any", [])],
                substitutions=_substitutions(r.get("substitutions", []), values),
                value=optional_value(r),
                paraphrase=fill(r["paraphrase"], params),
            )
            for r in raw.get("offline_rules", [])
        ],
        forbidden=[fill(v, params) for v in raw.get("forbidden", [])],
    )
