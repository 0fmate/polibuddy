"""Structured memory: a profile per student and anonymous session outcomes.

The chat is not stored: only which exercise, which typical mistake, how many attempts and the outcome.
Students are identified by a fingerprint (hash), never by name or student ID.
"""

from __future__ import annotations

import hashlib
import json
import time

from . import config

# How much help was needed before the plan worked, best first.
OUTCOMES = ["alone", "after_question", "after_slide", "with_hint", "unsolved"]


def anonymous(student: str) -> str:
    return hashlib.sha256(student.strip().lower().encode()).hexdigest()[:12]


def outcome_for_level(help_level: int) -> str:
    if help_level <= 1:
        return "alone"
    return {2: "after_question", 3: "after_slide"}.get(help_level, "with_hint")


def _profile_file(student: str):
    return config.RUNTIME_DIR / "students" / f"{anonymous(student)}.json"


def profile(student: str) -> dict:
    f = _profile_file(student)
    p = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    p.setdefault("solved", [])
    p.setdefault("outcomes", {})
    p.setdefault("attempted", [])
    return p


def _save(student: str, p: dict) -> None:
    f = _profile_file(student)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(p), encoding="utf-8")


def mark_attempted(student: str, exercise_id: str) -> None:
    p = profile(student)
    if exercise_id not in p["attempted"]:
        p["attempted"].append(exercise_id)
        _save(student, p)


def mark_solved(student: str, exercise_id: str, outcome: str = "alone") -> None:
    p = profile(student)
    if exercise_id not in p["solved"]:
        p["solved"].append(exercise_id)
    previous = p["outcomes"].get(exercise_id)
    # keep the best result: "alone" beats "with help"
    if previous is None or OUTCOMES.index(outcome) < OUTCOMES.index(previous):
        p["outcomes"][exercise_id] = outcome
    _save(student, p)


def topic_status(p: dict, exercise_id: str) -> str:
    """todo | in_progress | with_help | alone: the progress per topic shown in the chat."""
    outcome = p["outcomes"].get(exercise_id)
    if outcome == "alone":
        return "alone"
    if outcome:
        return "with_help"
    if exercise_id in p["attempted"]:
        return "in_progress"
    return "todo"


def record_session(student: str, exercise: str, topic: str, concepts: list[str],
                   mistake: str | None, attempts: int, outcome: str) -> None:
    config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "student": anonymous(student),
        "exercise": exercise,
        "topic": topic,
        "concepts": concepts,
        "mistake": mistake,
        "attempts": attempts,
        "outcome": outcome,
        "ts": int(time.time()),
        "simulated": False,
    }
    with (config.RUNTIME_DIR / "sessions.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def real_sessions() -> list[dict]:
    f = config.RUNTIME_DIR / "sessions.jsonl"
    if not f.exists():
        return []
    return [json.loads(r) for r in f.read_text(encoding="utf-8").splitlines() if r.strip()]


def log_step(session: str, event: str, data: dict) -> None:
    """Every step is logged: useful for debugging and as evidence in tests."""
    config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": round(time.time(), 3), "session": session, "event": event, **data}
    with (config.RUNTIME_DIR / "log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
