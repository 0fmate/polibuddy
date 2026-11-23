"""Plain ASCII maths -> LaTeX.

The model writes formulas as [[sin(3x)]], [[(3x)^3/6]], [[v0/g]]: no backslashes travel inside JSON
(where '\\frac' or '\\tan' would turn into control characters). They are converted here to $...$ LaTeX,
which the browser renders with KaTeX.
"""

from __future__ import annotations

import re

_OPERAND = r"(?:\([^()]*\)|[A-Za-z0-9_.]+)(?:\^(?:\([^()]*\)|-?[0-9a-z]+))?"
_FRACTION = re.compile(rf"({_OPERAND})\s*/\s*({_OPERAND})")


def _strip_parens(t: str) -> str:
    t = t.strip()
    if t.startswith("(") and t.endswith(")") and t.count("(") == 1:
        return t[1:-1]
    return t


def ascii_to_latex(s: str) -> str:
    s = s.strip().replace("≈", r" \approx ").replace("−", "-").replace("·", r" \cdot ").replace("*", r" \cdot ")
    s = re.sub(r"\blim\s*_?\s*\(?\s*x\s*->\s*0\s*\)?", r"\\lim_{x \\to 0} ", s)
    s = s.replace("->", r" \to ")
    s = re.sub(r"\bsqrt\s*\(([^()]*)\)", r"\\sqrt{\1}", s)
    s = re.sub(r"\b(sin|cos|tan|ln|exp)\b\s*", lambda m: "\\" + m.group(1) + " ", s)
    s = _FRACTION.sub(lambda m: r"\frac{%s}{%s}" % (_strip_parens(m.group(1)), _strip_parens(m.group(2))), s)
    s = re.sub(r"\b([a-z])0\b", r"\1_0", s)
    s = re.sub(r"\^\(([^()]*)\)", r"^{\1}", s)
    s = re.sub(r"\^(-?[0-9a-z]+)", r"^{\1}", s)
    return re.sub(r"\s+", " ", s).strip()


_CONTROL = {"\t": "\\t", "\x0c": "\\f", "\x08": "\\b", "\r": "\\r", "\x07": "\\a", "\x0b": "\\v"}


def repair(text: str) -> str:
    """Leftover control characters where a backslash should be."""
    return "".join(_CONTROL.get(c, "\\" if (ord(c) < 32 and c != "\n") or ord(c) == 127 else c) for c in text)


def to_latex(text: str) -> str:
    """Model text with [[ascii maths]] -> text with $LaTeX$."""
    text = repair(text)
    return re.sub(r"\[\[(.+?)\]\]", lambda m: "$" + ascii_to_latex(m.group(1)) + "$", text)
