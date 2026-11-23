"""Runs the student's plan with reliable tools (SymPy, mpmath, our own simulators).

The numbers shown to the student are computed here, never made up by the model.
Three engines: limit (substitutions + a table near 0), value (what happens with the proposed
value) and trace (the program run step by step by our simulator).
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

from .catalog import Exercise, Substitution, symbols, x
from .config import PRECISION_DIGITS, TABLE_POINTS

_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application, convert_xor)
_FUNCTIONS = {"e": sp.E, "E": sp.E, "pi": sp.pi, "tg": sp.tan, "ln": sp.log, "oo": sp.oo,
              "sqrt": sp.sqrt, "ceil": sp.ceiling, "ceiling": sp.ceiling, "floor": sp.floor}
_LITTLE_O = re.compile(r"[+-]?\s*\b[oO]\s*\([^()]*(\([^()]*\))*[^()]*\)")


def parse(text: str, values: dict | None = None) -> sp.Expr:
    """Parses an expression written by the model or by the offline rules.

    Little-o terms (o(x^3)) are dropped: they are a remainder, not something to compute.
    """
    clean = (
        text.replace("·", "*").replace("−", "-").replace("²", "**2").replace("³", "**3")
        .replace("√", "sqrt").replace("₀", "0").replace("infinity", "oo").replace(",", ".").strip()
    )
    clean = _LITTLE_O.sub("", clean).strip() or "0"
    values = values or {}
    loc = {**symbols(values), **_FUNCTIONS}
    e = parse_expr(clean, local_dict=loc, transformations=_TRANSFORMATIONS)
    return e.subs({sp.Symbol(k): sp.nsimplify(v) for k, v in values.items()})


def fmt_num(v: float | None, digits: int = 6) -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "—"
    return f"{v:.{digits}g}"


def fmt_value(expr: sp.Expr | None, digits: int = 4) -> str:
    if expr is None:
        return "—"
    if expr == sp.oo:
        return "infinity"
    if expr == -sp.oo:
        return "minus infinity"
    try:
        return fmt_num(float(expr), digits)
    except (TypeError, ValueError):
        return str(expr)


def evaluate(expr: sp.Expr, var: sp.Symbol, points: list[str]) -> list[float | None]:
    mp.mp.dps = PRECISION_DIGITS
    fn = sp.lambdify(var, expr, "mpmath")
    results: list[float | None] = []
    for p in points:
        try:
            v = float(fn(mp.mpf(p)))
            results.append(v if math.isfinite(v) else None)
        except (ZeroDivisionError, ValueError, TypeError, OverflowError):
            results.append(None)
    return results


def _curve(expr: sp.Expr, var: sp.Symbol, start: float, end: float, n: int = 120, skip_zero: bool = False):
    step = (end - start) / n
    xs = [round(start + i * step, 6) for i in range(n + 1)]
    if skip_zero:
        xs = [v for v in xs if abs(v) > 1e-9]
    ys = evaluate(expr, var, [repr(v) for v in xs])
    return [[xv, (yv if yv is not None and abs(yv) < 1e6 else None)] for xv, yv in zip(xs, ys)]


@dataclass
class Run:
    columns: list[str]
    rows: list[list[str]]
    predicted_label: str
    predicted: str
    observed_label: str
    observed: str
    works: bool
    chart: dict
    highlight: int | None = None
    true_values: list[float | None] = field(default_factory=list)  # for the buddy's lines
    not_applied: list[str] = field(default_factory=list)

    def public(self) -> dict:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "highlight": self.highlight,
            "predicted_label": self.predicted_label,
            "predicted": self.predicted,
            "observed_label": self.observed_label,
            "observed": self.observed,
            "works": self.works,
            "chart": self.chart,
        }


def apply_substitutions(f: sp.Expr, substitutions: list[Substitution]) -> tuple[sp.Expr, list[str]]:
    g = f
    not_applied: list[str] = []
    for old, new in substitutions:
        replaced = g.subs(old, new)
        if replaced == g:
            not_applied.append(str(old))
        g = replaced
    return g, not_applied


# ---------------------------------------------------------------- engine: limit

def _run_limit(ex: Exercise, substitutions: list[Substitution], predicted_text: str) -> Run:
    g: sp.Expr | None = None
    not_applied: list[str] = []
    if substitutions:
        g, not_applied = apply_substitutions(ex.f, substitutions)
        g = sp.simplify(g)

    predicted: sp.Expr | None = None
    if g is not None:
        predicted = sp.limit(g, x, 0)
    elif predicted_text.strip():
        try:
            predicted = parse(predicted_text, ex.values)
        except (sp.SympifyError, SyntaxError, TypeError):
            predicted = None

    true_vals = evaluate(ex.f, x, TABLE_POINTS)
    yours = evaluate(g, x, TABLE_POINTS) if g is not None else [None] * len(TABLE_POINTS)
    rows = [[fmt_num(float(p)), fmt_num(t, 9), fmt_num(y, 9)] for p, t, y in zip(TABLE_POINTS, true_vals, yours)]

    true_limit = sp.limit(ex.f, x, 0)  # stays on the server: never shown as a result
    works = predicted is not None and sp.simplify(predicted - true_limit) == 0
    last = next((v for v in reversed(true_vals) if v is not None), None)
    observed = fmt_num(last, 3)

    lines = []
    series = [{"points": _curve(ex.f, x, -0.6, 0.6, skip_zero=True), "role": "true", "label": "true function"}]
    if g is not None:
        series.append({"points": _curve(g, x, -0.6, 0.6, skip_zero=True), "role": "yours", "label": "your plan"})
    elif predicted is not None and predicted.is_finite:
        lines.append({"y": float(predicted), "role": "yours", "label": "your plan"})
    chart = {
        "x_min": -0.6, "x_max": 0.6, "x_label": "x", "series": series, "lines": lines,
        "marker": {"x": 0, "y": last, "text": f"→ {observed}", "role": "true"} if last is not None else None,
    }
    return Run(
        columns=["x", "true value", "your plan"],
        rows=rows,
        predicted_label="your plan predicts",
        predicted=fmt_value(predicted),
        observed_label="the numbers approach",
        observed=observed,
        works=bool(works),
        chart=chart,
        true_values=true_vals,
        not_applied=not_applied,
    )


# ---------------------------------------------------------------- engine: value

def _with_unit(v: float, unit: str) -> str:
    if abs(v) < 1e-6:  # numerical residue (5e-15 m) shown as zero
        v = 0.0
    return f"{fmt_num(v, 3)} {unit}".strip()


def _run_value(ex: Exercise, value: sp.Expr | None) -> Run:
    c = ex.cfg
    var = sp.Symbol(c["variable"])
    observable = parse(c["observable"], ex.values)
    target = float(parse(c["target"], ex.values))
    answer = float(ex.answer)
    v = float(value) if value is not None and value.is_real is not False else None
    if v is None or not math.isfinite(v) or v <= 0:
        v = None

    points = [v * k for k in (0.25, 0.5, 0.75, 1.0)] if v else []
    obs = evaluate(observable, var, [repr(p) for p in points]) if points else []
    obs = [0.0 if o is not None and abs(o) < 1e-6 else o for o in obs]
    rows = [[fmt_num(p, 3), fmt_num(o, 3), c.get("row_note", "") if i == len(points) - 1 else ""]
            for i, (p, o) in enumerate(zip(points, obs))]
    obs_at_v = obs[-1] if obs else None
    works = v is not None and abs(v - answer) <= 0.03 * abs(answer)

    end = max(1.25 * (v or 0), 1.12 * answer)
    marker = None
    if v is not None and obs_at_v is not None:
        marker = {"x": v, "y": obs_at_v, "text": c.get("row_note", "").replace("← ", ""), "role": "yours"}
    chart = {
        "x_min": 0, "x_max": end, "x_label": c.get("x_label", ""),
        "series": [{"points": _curve(observable, var, 0, end), "role": "true", "label": c.get("curve_label", "")}],
        "lines": [{"y": target, "role": "target", "label": c.get("target_label", "")}],
        "marker": marker,
    }
    return Run(
        columns=c["columns"],
        rows=rows,
        highlight=len(rows) - 1 if rows else None,
        predicted_label=c["predicted_label"],
        predicted=_with_unit(v, c.get("unit", "")) if v is not None else "—",
        observed_label=c["observed_label"],
        observed=_with_unit(obs_at_v, c.get("observable_unit", "")) if obs_at_v is not None else "—",
        works=works,
        chart=chart,
        true_values=obs,
    )


# ---------------------------------------------------------------- engine: trace

def _range_sum(n: int) -> tuple[list[list], int]:
    rows, s = [], 0
    for step, i in enumerate(range(1, n), start=1):
        s = s + i
        rows.append([step, i, s])
    return rows, s


def _while_count(n: int) -> tuple[list[list], int]:
    rows, i, count = [], 0, 0
    while i < n:
        count = count + 1
        rows.append([count, i, count])
        i = i + 2
    return rows, count


SIMULATORS = {"range_sum": _range_sum, "while_count": _while_count}


def _run_trace(ex: Exercise, value: sp.Expr | None) -> Run:
    c = ex.cfg
    trace, final = SIMULATORS[c["simulator"]](int(ex.values["n"]))
    v = None
    if value is not None:
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = None
    works = v is not None and abs(v - final) < 1e-9
    lines = [{"y": v, "role": "yours", "label": "your value"}] if v is not None else []
    chart = {
        "x_min": 0, "x_max": len(trace) + 0.5, "x_label": c.get("x_label", ""), "lines": lines,
        "series": [{"points": [[0, 0]] + [[r[0], r[2]] for r in trace], "role": "true",
                    "label": c.get("curve_label", ""), "show_points": True}],
        "marker": {"x": trace[-1][0], "y": final, "text": f"→ {final}", "role": "true"} if trace else None,
    }
    return Run(
        columns=c["columns"],
        rows=[[str(cell) for cell in r] for r in trace],
        highlight=len(trace) - 1 if trace else None,
        predicted_label=c["predicted_label"],
        predicted=fmt_num(v) if v is not None else "—",
        observed_label=c["observed_label"],
        observed=str(final),
        works=works,
        chart=chart,
        true_values=[float(r[2]) for r in trace],
    )


def run(ex: Exercise, substitutions: list[Substitution] | None = None, predicted_text: str = "",
        value: sp.Expr | None = None) -> Run:
    if ex.engine == "value":
        return _run_value(ex, value)
    if ex.engine == "trace":
        return _run_trace(ex, value)
    return _run_limit(ex, substitutions or [], predicted_text)
