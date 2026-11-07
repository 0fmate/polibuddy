# PoliBuddy

Prototype for the **Reply Student Tech Clash 2026 · AI on Campus** (Politecnico di Torino).

13.5% of Italian bachelor students drop out between the first and second year (ANVUR, 2026 Report).
PoliBuddy supports first-year students on the "wall" exams of the first year with one precise idea:
**not a tutor that corrects you, but a study buddy that runs your idea all the way** and shows you,
with real numbers, where it breaks. The teacher sees anonymously where the class gets stuck and,
before the exam, tests the exam draft against that data (Crash Test).

## Quick start (Windows)

```
avvia.bat
```

Or by hand:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn server:app --port 8000
```

Then open http://localhost:8000.

With `OPENAI_API_KEY` in `.env` it uses the model (`BUDDY_MODEL`, default `gpt-6-luna`): it understands freely
written plans, reads the whiteboard and photos, talks by voice and makes the buddy's lines more natural.
**It also works without a key**, in offline mode (catalogue rules). The badge at the top right shows the mode.

## Courses and exercises

| Course | Exercises | What PoliBuddy runs |
| --- | --- | --- |
| Calculus I | 4 Taylor limits (cosine, sine, exponential, tangent − sine) | Applies the student's substitution, computes the limit and a high-precision table near 0 (mpmath) |
| Physics I | Vertical throw, free fall | Computes what happens with the proposed value (e.g. at t = v₀/g the ball is still 20.4 m high) |
| Computer Science | Sum with `range`, counting with `while` | Runs the program step by step with our own simulator (never the student's code) |

Each student gets different numbers (from the student ID); the ID `demo` gets the demo numbers.
New exercises go in `data/catalogo.yaml`.

## Features

| Part | Where | What it does |
| --- | --- | --- |
| Interpreter | `buddy/interprete.py` | Understands the plan (typed, from the whiteboard, a photo or voice) and translates it into a structured form **without correcting it**. |
| Engine | `buddy/esecutore.py` | Three engines: limit, value, trace. Numbers are computed by code, never made up by the model. |
| Orchestrator | `buddy/orchestrator.py` | State machine: plan → confirmation → execution → comment. Decides how much help to give and the mascot state. |
| Buddy | `buddy/compagno.py` | PoliBuddy's lines: drafts in code, rephrased by the model; a rephrasing that reveals the solution or changes the numbers is discarded. |
| Formulas | `buddy/formule.py` + `web/app.js` | Every formula in the chat is rendered in LaTeX (KaTeX), including the maths students type (x^2, sin 3x, v0/g). |
| Voice | `buddy/voce.py` + `web/app.js` | Talk with PoliBuddy (mic button next to the attachment): speech-to-text, same pipeline as the chat, spoken reply, transcript at the end with a .txt download. |
| Attachments | `buddy/allegati.py` | Photos (read by the model), PDFs (text extracted with pypdf, offline too), text and code files. |
| Whiteboard | `buddy/lavagna.py` + `web/` | The student writes by hand; the model reads it and PoliBuddy repeats what it read before running it. |
| Memory | `buddy/memoria.py` | Profile and progress per topic, anonymous outcomes (hash), every step logged in `data/runtime/`. |
| Radar | `docente/radar.py` | Per course: pass rate by exercise type, mistakes found alone, most critical topic. Hidden below 10 sessions. |
| Crash Test | `docente/crash_test.py` | The exam draft against this term's data: concepts required and what the sessions say. |

**How much help:** after every plan that does not work, PoliBuddy helps a bit more: 1) shows the contradiction,
2) asks a targeted question on the typical mistake, 3) points to the slide, 4) gives a hint.
It never gives the solution; if the student asks for it, it answers "let's try your idea first".

**Mascot and progress:** the brand-kit mascot follows the session (studying the plan, "something doesn't add up",
try again, hint, success), and "Your progress" shows each topic of the course as to do, in progress,
solved with help or solved on your own.

## Demo script (2 minutes)

1. **Student** view, Calculus I, "Limit with sine" (student ID `demo`): lim (3x − sin 3x)/x³.
2. Click the suggestion "Near zero sin 3x is about 3x…": PoliBuddy restates the plan and asks for confirmation.
3. "Yes, exactly": the table fills up (4.4798 → 4.4998 → 4.49999998), the chart shows the true function
   going to 4.5 and the plan stuck at 0. Label "Doesn't add up".
4. Click "Just tell me the solution": PoliBuddy refuses and asks again (rule in code).
5. Click the mic and say "I expand sine of 3x up to x cubed": confirm by voice ("yes"), hear "It works!".
   End the conversation to get the transcript.
6. Switch to **Physics I** and attach a photo of a sheet with "t = v0/g": PoliBuddy reads it and shows that
   at 2.04 s the ball is still 20.4 m high.
7. **Teacher** view: pick the course, look at "Review in class" and press "Test the exam draft".

## Tests

```
.venv\Scripts\python -m pytest -q
```

They run offline: table to 4.5 even for tiny x, right and wrong plan for all 8 exercises, vertical throw and
`range` simulator, little-o terms ignored, ASCII-to-LaTeX formulas, LaTeX-to-speech, attachments, refusal of the
solution, discarding unsafe rephrasings, a full session with growing help, radar threshold, Crash Test.

## Known limits

- Slides in the catalogue are placeholders: link them to the real course material.
- Teacher data includes **simulated sessions** for the demo (stated on the page).
- Without a key the whiteboard, photos and voice are not available (PDFs and text files are; the browser's own
  speech recognition is used as a fallback where available).
- The Crash Test links questions to concepts by keywords.
- Sessions live in memory while the server runs; outcomes and logs go to `data/runtime/`.
- Code identifiers and comments are partly in Italian; everything the user sees is in English.
- The brand kit belongs to the PoliBuddy project and implies no affiliation with Politecnico di Torino.
