"""The calculation engine: numbers come from code, never from the model."""

from __future__ import annotations

import pytest

from buddy import catalog, engine

ALL_EXERCISES = ["lim-cosine", "lim-sine", "lim-exponential", "lim-tangent",
                 "phys-throw", "phys-fall", "cs-range", "cs-while"]


def test_wrong_plan_predicts_zero_but_numbers_approach_4_5(sine):
    result = engine.run(sine, sine.mistakes[0].substitutions)
    assert result.predicted == "0"
    assert result.observed == "4.5"
    assert not result.works
    assert abs(result.true_values[-1] - 4.5) < 1e-6


def test_high_precision_even_for_tiny_x(sine):
    """With ordinary floats the numerator vanishes below 1e-7: with mpmath it does not."""
    value = engine.evaluate(sine.f, catalog.x, ["1e-9"])[0]
    assert value is not None and abs(value - 4.5) < 1e-9


def test_right_plan_works(sine):
    result = engine.run(sine, sine.rules[0].substitutions)
    assert result.works and result.predicted == "4.5"


@pytest.mark.parametrize("exercise_id", ALL_EXERCISES)
def test_every_exercise_has_a_typical_mistake_and_a_right_plan(exercise_id):
    ex = catalog.load(exercise_id, "demo")
    mistake, right = ex.mistakes[0], ex.rules[0]
    assert not engine.run(ex, mistake.substitutions, value=mistake.value).works
    assert engine.run(ex, right.substitutions, value=right.value).works


def test_vertical_throw_with_the_time_to_the_top():
    ex = catalog.load("phys-throw", "demo")  # v0 = 20 m/s
    result = engine.run(ex, value=ex.mistakes[0].value)
    assert result.predicted == "2.04 s" and result.observed == "20.4 m" and not result.works


def test_range_run_by_the_simulator():
    ex = catalog.load("cs-range", "demo")  # n = 10
    result = engine.run(ex, value=ex.mistakes[0].value)
    assert result.predicted == "55" and result.observed == "45" and len(result.rows) == 9


def test_little_o_is_ignored():
    assert engine.parse("3*x - 27*x**3/6 + o(x**3)") == engine.parse("3*x - 9*x**3/2")


def test_different_numbers_per_student_and_fixed_demo():
    assert catalog.load("lim-sine", "demo").param == 3
    params = {catalog.load("lim-sine", f"s{i:06d}").param for i in range(30)}
    assert len(params) > 1


def test_chart_payload_is_json_ready(sine):
    import json

    chart = engine.run(sine, sine.mistakes[0].substitutions).public()["chart"]
    json.dumps(chart)
    assert {s["role"] for s in chart["series"]} == {"true", "yours"}
