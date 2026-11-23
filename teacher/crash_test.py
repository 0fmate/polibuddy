"""Crash Test on the data: the draft exam against the mistakes collected during the semester.

Each question is linked to catalog concepts (by keyword) and reports what the sessions say
about those concepts. The teacher always decides.
"""

from __future__ import annotations

import re

from buddy.catalog import concepts
from buddy.config import MIN_SESSIONS

from .radar import all_sessions

DEMO_QUESTIONS = {
    "calculus1": [
        "Compute the limit as x → 0 of (2x − sin 2x) / x³",
        "Compute the limit as x → 0 of (1 − cos 4x) / x²",
        "Study the convergence of the series with general term 1/n²",
        "Compute the limit as x → 0 of (tan x − sin x) / x³",
    ],
    "physics1": [
        "A ball is thrown upward at 15 m/s: after how long is it back to the ground?",
        "A body is dropped from rest from 45 m: how fast does it hit the ground?",
        "Compute the moment of inertia of a uniform disc about its axis",
    ],
    "cs": [
        "What does this program print: for i in range(2, 8): print(i)",
        "How many iterations does it run: i = 0; while i < 9: i = i + 2",
        "Write a recursive function that computes the factorial of n",
    ],
}

ATTENTION_THRESHOLD = 40  # % of mistakes found alone below which a question is flagged


def find_concepts(question: str) -> list[str]:
    text = question.lower()
    found = []
    for cid, c in concepts().items():
        for key in c["keywords"]:
            key = key.strip().lower()
            if key.endswith("*"):  # prefix: thrown* matches "thrown"
                pattern = rf"\b{re.escape(key[:-1])}"
            elif key.isalnum():
                pattern = rf"\b{re.escape(key)}\b"
            else:
                pattern = re.escape(key)
            if re.search(pattern, text):
                found.append(cid)
                break
    return found


def analyze(questions: list[str]) -> list[dict]:
    sessions = all_sessions()
    known = concepts()
    report = []
    for i, question in enumerate(q.strip()[:500] for q in questions[:30] if q.strip()):
        cids = find_concepts(question)
        item = {"number": i + 1, "question": question, "concepts": [known[c]["name"] for c in cids]}
        if not cids:
            item.update(status="no_data", text="No sessions on this topic: we do not know how prepared the class is.")
            report.append(item)
            continue

        details = []
        worst = None
        for cid in cids:
            name = known[cid]["name"]
            mine = [s for s in sessions if cid in s["concepts"]]
            with_mistake = [s for s in mine if s["attempts"] > 0]
            if len(mine) < MIN_SESSIONS or not with_mistake:
                details.append(f"{name}: only {len(mine)} sessions, not enough data")
                worst = worst if worst is not None else -1
                continue
            pct = round(100 * sum(s["outcome"] == "alone" for s in with_mistake) / len(with_mistake))
            details.append(f"{name}: in {len(with_mistake)} sessions with a mistake, found alone in {pct}% of cases")
            worst = pct if worst in (None, -1) else min(worst, pct)

        if worst == -1:
            status, advice = "not_enough", "Not enough data to give an indication."
        elif worst < ATTENTION_THRESHOLD:
            status = "attention"
            advice = "Consider a targeted practice session before the exam, or keep the difficulty if it is intended."
        else:
            status, advice = "ok", "In line with the preparation shown in the sessions."
        item.update(status=status, text="; ".join(details) + ". " + advice)
        report.append(item)
    return report
