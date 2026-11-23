"""PoliBuddy's lines and the in-code safety checks.

Every line starts from a draft written here (reliable). If a model is available, the draft is
rephrased more naturally, but the rephrasing must pass a check: if it reveals the solution or
changes the numbers, it is discarded and the draft is used.
Formulas are written in LaTeX between $...$ and rendered by the browser.
"""

from __future__ import annotations

import re

from . import config, llm
from .catalog import Exercise, Mistake
from .engine import Run, fmt_num

_ASKS_FOR_SOLUTION = re.compile(
    r"(tell\s+me|give\s+me|show\s+me|what'?s|what\s+is|just\s+tell)\b.{0,30}(solution|answer|result|limit)"
    r"|solve\s+it\s+(for\s+me|yourself)|you\s+do\s+it|just\s+give\s+me|i\s+don'?t\s+know,?\s+tell\s+me",
    re.IGNORECASE,
)

SOLUTION_REFUSAL = (
    "Let's try your idea first: how would you solve it? "
    "It's fine if you're not sure, I'll do the maths."
)

_ALWAYS_FORBIDDEN = [
    "the limit is", "the limit equals", "the answer is", "the solution is", "the result is",
    "correct answer", "correct procedure", "the right answer",
]

SYSTEM_PROMPT = """You are PoliBuddy: a study buddy for a first-year engineering student, not a professor.
You receive a DRAFT of your next line and rephrase it naturally.

Rules:
- English, at most 3 short sentences, friendly peer tone.
- Keep EXACTLY all the numbers of the draft, written the same way.
- Keep every formula in LaTeX between $...$, exactly as in the draft.
- Do not add information, formulas, hints or steps that are not in the draft.
- Never state the solution and never reveal the correct method:
  you may only describe what the numbers in the table show.
- Reply with the line only, no quotes."""

_LIMIT_LINES = {
    "contradiction_line": "If you were right, as we get close to zero we should see numbers close to {predicted}. "
                          "Instead, look: {first}… they approach {observed}.",
    "still_wrong_line": "your plan gives {predicted}, but the numbers approach {observed}.",
    "works_line": "your plan gives {predicted}, and the numbers really approach {observed}.",
}


def asks_for_solution(text: str) -> bool:
    return bool(_ASKS_FOR_SOLUTION.search(text))


def is_safe(line: str, ex: Exercise, draft: str) -> bool:
    """True if the rephrased line is safe to show."""
    low = line.lower()
    if any(f in low for f in _ALWAYS_FORBIDDEN):
        return False
    if any(f.lower() in low for f in ex.forbidden if f.lower() not in draft.lower()):
        return False
    draft_numbers = set(re.findall(r"\d+(?:\.\d+)?", draft))
    line_numbers = set(re.findall(r"\d+(?:\.\d+)?", line))
    # every number of the draft must stay, and no new ones may appear
    return draft_numbers == line_numbers


def rephrase(draft: str, ex: Exercise) -> str:
    if not (config.REPHRASE and llm.available()):
        return draft
    for _ in range(2):
        proposal = llm.text(SYSTEM_PROMPT, f"Draft: {draft}", max_tokens=1500)
        if proposal and is_safe(proposal, ex, draft):
            return proposal
    return draft


# --- Drafts ------------------------------------------------------------------

def welcome(ex: Exercise) -> str:
    where = "the code above" if ex.code else "the exercise above"
    return (
        f"Hi! Let's try this one: {ex.text} (see {where}). How would you solve it? "
        "Tell me your plan, even roughly: you can use the whiteboard, attach a photo of your sheet or just talk to me."
    )


def explain_again() -> str:
    return "Okay, then explain it again: what do you want to do, step by step?"


def substitution_not_found(expr: str) -> str:
    return f"I tried to follow your plan, but ${expr}$ does not appear in the exercise. Can you rewrite it?"


def _line(ex: Exercise, key: str, result: Run) -> str:
    template = ex.cfg.get(key) or _LIMIT_LINES[key]
    first = ", ".join(fmt_num(v, 5) for v in result.true_values[:3] if v is not None)
    return template.replace("{predicted}", result.predicted).replace("{observed}", result.observed).replace("{first}", first)


def after_run(ex: Exercise, result: Run, help_level: int, attempts: int, mistake: Mistake | None = None) -> str:
    if result.works:
        detail = _line(ex, "works_line", result)
        if attempts == 0:
            return f"It works on the first try: {detail} Want to try a harder one?"
        return f"It works! {detail[0].upper()}{detail[1:]} You found the mistake yourself. Want to try another one?"

    if result.predicted == "—":
        observation = (
            "I tried your plan, but it doesn't lead to a precise value. "
            f"Meanwhile, look at the table: {result.observed_label} {result.observed}."
        )
    elif help_level <= 1:
        return f"Okay, let's try it your way. {_line(ex, 'contradiction_line', result)} Weird, where did we lose it?"
    else:
        observation = f"Still not right: {_line(ex, 'still_wrong_line', result)}"

    if help_level <= 1:
        return f"{observation} Where do you think the problem is?"
    if help_level == 2:
        question = mistake.targeted_question if mistake else "Which step of your plan convinces you the least?"
        return f"{observation} {question}"
    if help_level == 3:
        return f"{observation} I suggest rereading this: {ex.slide}. Then try again with your own idea."
    hint = (mistake.hint if mistake else None) or (ex.mistakes[0].hint if ex.mistakes else "Start again from the definition.")
    return f"{observation} A hint: {hint} The rest is up to you."
