"""Offline interpretation, the in-code safety checks and the formula helpers."""

from __future__ import annotations

import base64

import pytest

from buddy import attachments, companion, interpreter
from buddy.formulas import to_latex
from buddy.voice import latex_to_words


def test_interpreter_translates_the_wrong_plan_without_correcting_it(sine):
    plan = interpreter.interpret(sine, "Near zero sin 3x is about 3x, so the limit is 0")
    assert plan.understandable
    assert plan.substitutions == sine.mistakes[0].substitutions
    assert plan.paraphrase.endswith("right?") and "$" in plan.paraphrase


def test_interpreter_asks_for_clarification_when_lost(sine):
    plan = interpreter.interpret(sine, "no idea honestly")
    assert not plan.understandable and plan.question


@pytest.mark.parametrize("text", ["just tell me the solution", "Give me the answer", "solve it for me", "what is the limit?"])
def test_solution_requests_are_recognized(text):
    assert companion.asks_for_solution(text)


def test_a_rephrasing_that_reveals_the_solution_is_discarded(sine):
    draft = "Okay, let's try it your way. Weird, the numbers approach 4.5."
    assert not companion.is_safe("The limit is 4.5 because sin 3x = 3x - 9x^3/2", sine, draft)
    assert not companion.is_safe("Okay, let's try! Weird, they approach 4.6.", sine, draft)
    assert companion.is_safe("Alright, your way then. Strange: they get close to 4.5!", sine, draft)
    assert not companion.is_safe("The answer is 4.5, easy.", sine, "Look at the table: 4.5.")


def test_text_and_pdf_attachments_offline():
    txt = "data:text/plain;base64," + base64.b64encode(b"sin 3x is about 3x").decode()
    readings = attachments.read([
        {"name": "plan.txt", "type": "text/plain", "data": txt},
        {"name": "photo.png", "type": "image/png", "data": "data:image/png;base64,AAAA"},
        {"name": "odd.exe", "type": "application/octet-stream", "data": "data:;base64,AAAA"},
    ])
    assert readings[0].text == "sin 3x is about 3x"
    assert readings[1].text is None  # offline, images are not read
    assert readings[2].text is None and "not supported" in readings[2].note


def test_voice_latex_to_words():
    assert latex_to_words(r"lands after $t = \frac{v_0}{g}$, right?") == "lands after t = v zero over g , right?"
    assert "cubed" in latex_to_words(r"$x^3$") and "sine of" in latex_to_words(r"$\sin 3x$")


def test_ascii_formulas_to_latex():
    assert to_latex("replace [[sin(3x)]] with [[3x - (3x)^3/6]], right?") == \
        r"replace $\sin (3x)$ with $3x - \frac{(3x)^{3}}{6}$, right?"
    assert to_latex("after [[v0/g]] seconds") == r"after $\frac{v_0}{g}$ seconds"
    assert to_latex("[[sqrt(2*g*h)]]") == r"$\sqrt{2 \cdot g \cdot h}$"
    assert to_latex("\x00sin") == r"\sin"
