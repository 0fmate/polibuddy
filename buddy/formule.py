"""Plain ASCII maths -> LaTeX.

The model writes formulas as [[sin(3x)]], [[(3x)^3/6]], [[v0/g]]: no backslashes travel inside JSON
(where '\\frac' or '\\tan' would turn into control characters). We convert them here to $...$ LaTeX,
which the browser renders with KaTeX.
"""

from __future__ import annotations

import re

_OPERANDO = r"(?:\([^()]*\)|[A-Za-z0-9_.]+)(?:\^(?:\([^()]*\)|-?[0-9a-z]+))?"
_FRAZIONE = re.compile(rf"({_OPERANDO})\s*/\s*({_OPERANDO})")


def _senza_parentesi(t: str) -> str:
    t = t.strip()
    if t.startswith("(") and t.endswith(")") and t.count("(") == 1:
        return t[1:-1]
    return t


def ascii_a_latex(s: str) -> str:
    s = s.strip().replace("≈", r" \approx ").replace("−", "-").replace("·", r" \cdot ").replace("*", r" \cdot ")
    s = re.sub(r"\blim\s*_?\s*\(?\s*x\s*->\s*0\s*\)?", r"\\lim_{x \\to 0} ", s)
    s = s.replace("->", r" \to ")
    s = re.sub(r"\bsqrt\s*\(([^()]*)\)", r"\\sqrt{\1}", s)
    s = re.sub(r"\b(sin|cos|tan|ln|exp)\b\s*", lambda m: "\\" + m.group(1) + " ", s)
    s = _FRAZIONE.sub(lambda m: r"\frac{%s}{%s}" % (_senza_parentesi(m.group(1)), _senza_parentesi(m.group(2))), s)
    s = re.sub(r"\b([a-z])0\b", r"\1_0", s)
    s = re.sub(r"\^\(([^()]*)\)", r"^{\1}", s)
    s = re.sub(r"\^(-?[0-9a-z]+)", r"^{\1}", s)
    return re.sub(r"\s+", " ", s).strip()


_CONTROLLO = {"\t": "\\t", "\x0c": "\\f", "\x08": "\\b", "\r": "\\r", "\x07": "\\a", "\x0b": "\\v"}


def ripara(testo: str) -> str:
    """Leftover control characters where a backslash should be."""
    return "".join(_CONTROLLO.get(c, "\\" if (ord(c) < 32 and c != "\n") or ord(c) == 127 else c) for c in testo)


def in_latex(testo: str) -> str:
    """Model text with [[ascii maths]] -> text with $LaTeX$."""
    testo = ripara(testo)
    return re.sub(r"\[\[(.+?)\]\]", lambda m: "$" + ascii_a_latex(m.group(1)) + "$", testo)
