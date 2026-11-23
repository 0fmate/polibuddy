"""The student's session as a state machine.

The code decides the phases (plan -> confirmation -> run -> comment) and how much rope to give;
the model understands the plan and gives the buddy a voice, but never decides when the work is done.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

import sympy as sp

from . import attachments, companion, interpreter, memory, whiteboard
from .catalog import Exercise, Mistake, courses, load, raw_exercises
from .config import MAX_HELP_LEVEL
from .engine import apply_substitutions, run

_YES = re.compile(r"^\s*(yes|yeah|yep|yup|right|correct|exactly|ok|okay|sure|confirm|that'?s right)\b", re.I)
_NO = re.compile(r"^\s*(no|nope|not|wrong|wait|hold on)\b", re.I)

# Mascot moods (files in web/brand/mascot/)
MOOD_AFTER_MISTAKE = {1: "thinking", 2: "retry", 3: "retry", 4: "idea"}
MAX_SESSIONS = 2000


@dataclass
class Session:
    id: str
    student: str
    exercise: Exercise
    state: str = "awaiting_plan"  # awaiting_plan | awaiting_confirmation | solved
    attempts: int = 0
    help_level: int = 0
    pending: interpreter.Interpretation | None = None
    mistake: Mistake | None = None
    recorded: bool = False
    source: str = "rules"
    mood: str = "default"
    messages: list[dict] = field(default_factory=list)


SESSIONS: dict[str, Session] = {}


def _ids(course: str | None) -> list[str]:
    return [e["id"] for e in raw_exercises(course)]


def pick_exercise(student: str, preferred: str | None = None, course: str | None = None) -> str:
    if preferred in _ids(None):
        return preferred
    course = course if course in courses() else "calculus1"
    ids = _ids(course)
    solved = set(memory.profile(student)["solved"])
    # adaptive difficulty: the first exercise not solved yet, ordered by level
    return next((i for i in ids if i not in solved), ids[-1])


def progress(student: str, course: str) -> list[dict]:
    p = memory.profile(student)
    return [
        {"id": e["id"], "title": e["title"], "level": e["level"], "status": memory.topic_status(p, e["id"])}
        for e in raw_exercises(course)
    ]


def _reply(s: Session, texts: list[str], result=None, whiteboard_text: str | None = None,
           readings: list | None = None) -> dict:
    for t in texts:
        s.messages.append({"role": "buddy", "text": t})
    return {
        "session": s.id,
        "exercise": s.exercise.public(),
        "messages": texts,
        "state": s.state,
        "mood": s.mood,
        "attempts": s.attempts,
        "help_level": s.help_level,
        "max_help_level": MAX_HELP_LEVEL,
        "run": result.public() if result else None,
        "whiteboard_text": whiteboard_text,
        "attachments": [r.public() for r in (readings or [])],
        "progress": progress(s.student, s.exercise.course),
        "source": s.source,
    }


def new_session(student: str, exercise: str | None = None, course: str | None = None) -> dict:
    student = (student or "").strip()[:64] or "demo"
    ex = load(pick_exercise(student, exercise, course), student)
    s = Session(id=uuid.uuid4().hex[:12], student=student, exercise=ex)
    if len(SESSIONS) >= MAX_SESSIONS:  # public demo: keep memory bounded
        SESSIONS.pop(next(iter(SESSIONS)))
    SESSIONS[s.id] = s
    memory.log_step(s.id, "start", {"exercise": ex.id, "values": ex.values})
    return _reply(s, [companion.welcome(ex)])


def _same(a: sp.Expr | None, b: sp.Expr | None) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return sp.simplify(a - b) == 0


def _recognize_mistake(ex: Exercise, plan: interpreter.Interpretation) -> Mistake | None:
    """The typical mistake from the catalog that matches the student's plan."""
    for m in ex.mistakes:
        if m.value is not None:
            if _same(plan.value, m.value):
                return m
            continue
        if not m.substitutions or len(m.substitutions) != len(plan.substitutions):
            continue
        if all(
            any(sp.simplify(o1 - o2) == 0 and sp.simplify(n1 - n2) == 0 for o2, n2 in plan.substitutions)
            for o1, n1 in m.substitutions
        ):
            return m
    return None


def _record(s: Session, outcome: str) -> None:
    if s.recorded:
        return
    memory.record_session(
        s.student, s.exercise.id, s.exercise.topic, s.exercise.concepts,
        s.mistake.id if s.mistake else None, s.attempts, outcome,
    )
    s.recorded = True


def _run_plan(s: Session) -> dict:
    plan = s.pending
    assert plan is not None
    result = run(s.exercise, plan.substitutions, plan.predicted_limit, plan.value)
    memory.log_step(s.id, "run", {"predicted": result.predicted, "works": result.works, "observed": result.observed})
    s.pending = None

    if result.works:
        draft = companion.after_run(s.exercise, result, s.help_level, s.attempts, s.mistake)
        s.state = "solved"
        s.mood = "success"
        outcome = memory.outcome_for_level(s.help_level)
        _record(s, outcome)
        memory.mark_solved(s.student, s.exercise.id, outcome)
    else:
        s.attempts += 1
        s.help_level = min(s.attempts, MAX_HELP_LEVEL)
        recognized = _recognize_mistake(s.exercise, plan)
        s.mistake = s.mistake or recognized
        draft = companion.after_run(s.exercise, result, s.help_level, s.attempts, recognized)
        s.state = "awaiting_plan"
        s.mood = MOOD_AFTER_MISTAKE[s.help_level]
        memory.mark_attempted(s.student, s.exercise.id)
    return _reply(s, [companion.rephrase(draft, s.exercise)], result=result)


def message(session_id: str, text: str = "", whiteboard_png: str | None = None,
            files: list[dict] | None = None) -> dict:
    s = SESSIONS[session_id]
    text = (text or "").strip()[:4000]
    files = files or []
    s.messages.append({"role": "student", "text": text})
    memory.log_step(s.id, "message", {
        "text": text, "whiteboard": bool(whiteboard_png), "files": [f.get("name") for f in files], "state": s.state,
    })

    # A limit enforced in code: the solution is never handed over, it is built.
    if text and companion.asks_for_solution(text):
        memory.log_step(s.id, "solution_refused", {"text": text})
        s.mood = "default"
        return _reply(s, [companion.SOLUTION_REFUSAL])

    # A confirmation ("yes" / "no") counts even if the browser attaches the whiteboard.
    if s.state == "awaiting_confirmation" and text and not files:
        if _YES.match(text):
            return _run_plan(s)
        if _NO.match(text) and len(text) < 25:
            s.pending = None
            s.state = "awaiting_plan"
            s.mood = "thinking"
            return _reply(s, [companion.explain_again()])
        # otherwise it is treated as a new plan

    board = whiteboard.read(whiteboard_png) if whiteboard_png else None
    readings = attachments.read(files) if files else []
    extra = "\n".join(filter(None, [
        f"(Written on the whiteboard: {board})" if board else "",
        attachments.as_text(readings),
    ]))

    if not text and not extra:
        if readings or whiteboard_png:
            note = "; ".join(f"{r.name}: {r.note}" for r in readings) if readings else \
                "I cannot read the whiteboard here (no vision model, or it is empty)"
            return _reply(s, [f"I cannot use what you sent me ({note}). Please type your plan below as well."],
                          whiteboard_text=board, readings=readings)
        return _reply(s, ["Tell me your plan: how would you solve it?"])

    plan = interpreter.interpret(s.exercise, text, extra)
    s.source = plan.source
    memory.log_step(s.id, "interpretation", {
        "source": plan.source, "understandable": plan.understandable, "value": str(plan.value),
        "substitutions": [f"{o} -> {n}" for o, n in plan.substitutions], "predicted": plan.predicted_limit,
    })
    if not plan.understandable:
        s.mood = "thinking"
        return _reply(s, [plan.question], whiteboard_text=board, readings=readings)

    if plan.substitutions and s.exercise.f is not None:
        _, not_applied = apply_substitutions(s.exercise.f, plan.substitutions)
        if not_applied and len(not_applied) == len(plan.substitutions):
            s.mood = "thinking"
            return _reply(s, [companion.substitution_not_found(not_applied[0])], whiteboard_text=board, readings=readings)

    s.pending = plan
    s.state = "awaiting_confirmation"
    s.mood = "studying"
    return _reply(s, [plan.paraphrase], whiteboard_text=board, readings=readings)


def next_exercise(session_id: str) -> dict:
    s = SESSIONS[session_id]
    if s.state != "solved" and s.attempts > 0:
        _record(s, "unsolved")
    ids = _ids(s.exercise.course)
    solved = set(memory.profile(s.student)["solved"])
    i = ids.index(s.exercise.id)
    after = ids[i + 1:] + ids[: i + 1]
    following = next((e for e in after if e not in solved), after[0])
    return new_session(s.student, following)
