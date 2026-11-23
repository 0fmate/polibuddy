"""Teacher radar: anonymous, aggregated data, shown only above a minimum number of sessions.

For the demo, real sessions are added to a set of SIMULATED sessions (stated on the page).
"""

from __future__ import annotations

from collections import Counter

from buddy.catalog import courses, raw_exercises
from buddy.config import MIN_SESSIONS
from buddy.memory import OUTCOMES, real_sessions

# Simulated profiles: (sessions, solved on the first try, split of outcomes for those who made a mistake).
_SIMULATED_PROFILES = {
    "lim-cosine": (46, 16, {"alone": 0.60, "after_question": 0.25, "after_slide": 0.08, "with_hint": 0.04, "unsolved": 0.03}),
    "lim-sine": (120, 18, {"alone": 0.30, "after_question": 0.32, "after_slide": 0.18, "with_hint": 0.12, "unsolved": 0.08}),
    "lim-exponential": (64, 14, {"alone": 0.45, "after_question": 0.30, "after_slide": 0.12, "with_hint": 0.08, "unsolved": 0.05}),
    "lim-tangent": (8, 1, {"alone": 0.25, "after_question": 0.25, "after_slide": 0.25, "with_hint": 0.125, "unsolved": 0.125}),
    "phys-throw": (84, 12, {"alone": 0.25, "after_question": 0.35, "after_slide": 0.2, "with_hint": 0.12, "unsolved": 0.08}),
    "phys-fall": (52, 15, {"alone": 0.5, "after_question": 0.3, "after_slide": 0.1, "with_hint": 0.06, "unsolved": 0.04}),
    "cs-range": (140, 30, {"alone": 0.55, "after_question": 0.3, "after_slide": 0.08, "with_hint": 0.05, "unsolved": 0.02}),
    "cs-while": (63, 10, {"alone": 0.35, "after_question": 0.33, "after_slide": 0.17, "with_hint": 0.1, "unsolved": 0.05}),
}


def simulated_sessions() -> list[dict]:
    rows: list[dict] = []
    for raw in raw_exercises():
        profile = _SIMULATED_PROFILES.get(raw["id"])
        if not profile:
            continue
        n, first_try, split = profile
        mistake = raw["mistakes"][0]["id"] if raw.get("mistakes") else None
        base = {"exercise": raw["id"], "topic": raw["topic"], "concepts": raw["concepts"], "simulated": True}
        rows += [{**base, "mistake": None, "attempts": 0, "outcome": "alone"} for _ in range(first_try)]
        with_mistake = n - first_try
        counts = {k: round(v * with_mistake) for k, v in split.items()}
        counts["alone"] += with_mistake - sum(counts.values())  # rounding
        for outcome, c in counts.items():
            rows += [{**base, "mistake": mistake, "attempts": 1 + OUTCOMES.index(outcome), "outcome": outcome}
                     for _ in range(c)]
    return rows


def all_sessions() -> list[dict]:
    return simulated_sessions() + real_sessions()


def _pct(part: int, total: int) -> int:
    return round(100 * part / total) if total else 0


def aggregate(course: str = "calculus1") -> dict:
    course = course if course in courses() else "calculus1"
    ids = {e["id"] for e in raw_exercises(course)}
    sessions = [s for s in all_sessions() if s["exercise"] in ids]
    mistake_names = {m["id"]: m["name"] for r in raw_exercises() for m in r.get("mistakes", [])}
    rows = []
    for raw in raw_exercises(course):
        mine = [s for s in sessions if s["exercise"] == raw["id"]]
        n = len(mine)
        row = {"id": raw["id"], "title": raw["title"], "topic": raw["topic"], "level": raw["level"],
               "n": n, "enough": n >= MIN_SESSIONS}
        if row["enough"]:
            with_mistake = [s for s in mine if s["attempts"] > 0]
            outcomes = Counter(s["outcome"] for s in with_mistake)
            top = Counter(s["mistake"] for s in with_mistake if s["mistake"]).most_common(1)
            row.update({
                "first_try_pct": _pct(n - len(with_mistake), n),
                "n_with_mistake": len(with_mistake),
                "outcomes_pct": {o: _pct(outcomes.get(o, 0), len(with_mistake)) for o in OUTCOMES},
                "alone_pct": _pct(outcomes.get("alone", 0), len(with_mistake)),
                "main_mistake": mistake_names.get(top[0][0], "") if top else "",
            })
        rows.append(row)

    valid = [r for r in rows if r["enough"]]
    with_mistake_total = sum(r["n_with_mistake"] for r in valid)
    alone_total = sum(round(r["alone_pct"] * r["n_with_mistake"] / 100) for r in valid)
    first_total = sum(round(r["first_try_pct"] * r["n"] / 100) for r in valid)
    gaps = sorted(valid, key=lambda r: r["alone_pct"])[:2]
    critical = gaps[0] if gaps else None
    return {
        "course": course,
        "course_name": courses()[course]["name"],
        "courses": [{"id": k, "name": v["name"]} for k, v in courses().items()],
        "critical": {"title": critical["title"], "alone_pct": critical["alone_pct"]} if critical else None,
        "min_sessions": MIN_SESSIONS,
        "total_sessions": len(sessions),
        "real_sessions": sum(1 for s in sessions if not s.get("simulated")),
        "first_try_pct": _pct(first_total, sum(r["n"] for r in valid)),
        "alone_pct": _pct(alone_total, with_mistake_total),
        "exercises": rows,
        "gaps": [
            {"title": r["title"], "mistake": r["main_mistake"], "alone_pct": r["alone_pct"], "n": r["n_with_mistake"]}
            for r in gaps
        ],
        "outcomes": OUTCOMES,
    }
