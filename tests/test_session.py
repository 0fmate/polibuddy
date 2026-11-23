"""A full student session, the teacher views and the HTTP API."""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from buddy import companion, config, memory, orchestrator


def test_full_session_with_growing_help():
    r = orchestrator.new_session("demo", "lim-sine")
    sid = r["session"]

    r = orchestrator.message(sid, "just tell me the solution")
    assert r["messages"] == [companion.SOLUTION_REFUSAL] and r["state"] == "awaiting_plan"

    wrong = "Near zero sin 3x is about 3x, so the numerator is zero"
    for expected in (1, 2, 3, 4, 4):
        r = orchestrator.message(sid, wrong)
        assert r["state"] == "awaiting_confirmation"
        r = orchestrator.message(sid, "yes")
        assert r["run"]["works"] is False
        assert r["help_level"] == expected

    orchestrator.message(sid, "sin 3x ≈ 3x - (3x)^3/6")
    r = orchestrator.message(sid, "yes, exactly", whiteboard_png="data:image/png;base64,AAAA")
    assert r["state"] == "solved" and r["run"]["works"]

    assert r["mood"] == "success"
    assert next(p for p in r["progress"] if p["id"] == "lim-sine")["status"] == "with_help"
    rows = memory.real_sessions()
    assert len(rows) == 1
    assert rows[0]["mistake"] == "sine-first-order" and rows[0]["outcome"] == "with_hint"
    assert rows[0]["student"] != "demo"  # anonymous


def test_session_with_an_attached_file():
    r = orchestrator.new_session("demo", "lim-sine")
    txt = "data:text/plain;base64," + base64.b64encode(b"sin 3x is about 3x").decode()
    r = orchestrator.message(r["session"], "", files=[{"name": "plan.txt", "type": "text/plain", "data": txt}])
    assert r["state"] == "awaiting_confirmation" and r["attachments"][0]["ok"]


def test_radar_hides_data_below_the_threshold():
    from teacher import radar

    data = radar.aggregate("calculus1")
    tangent = next(e for e in data["exercises"] if e["id"] == "lim-tangent")
    assert tangent["n"] < config.MIN_SESSIONS and not tangent["enough"]
    assert "alone_pct" not in tangent


def test_crash_test_flags_uncovered_and_weak_topics():
    from teacher import crash_test

    expected = {
        "calculus1": ["attention", "ok", "no_data", "attention"],
        "physics1": ["attention", "ok", "no_data"],
        "cs": ["ok", "attention", "no_data"],
    }
    for course, statuses in expected.items():
        assert [item["status"] for item in crash_test.analyze(crash_test.DEMO_QUESTIONS[course])] == statuses


def test_api_round_trip_and_rate_limit(monkeypatch):
    from server import app

    client = TestClient(app)
    status = client.get("/api/status").json()
    assert status["mode"] == "offline" and {c["id"] for c in status["courses"]} == {"calculus1", "physics1", "cs"}

    sid = client.post("/api/session", json={"student": "demo", "exercise": "phys-throw"}).json()["session"]
    r = client.post("/api/message", json={"session": sid, "text": "t = v0/g"}).json()
    assert r["state"] == "awaiting_confirmation"
    r = client.post("/api/message", json={"session": sid, "text": "yes"}).json()
    assert r["run"]["works"] is False

    assert client.post("/api/message", json={"session": "nope", "text": "hi"}).status_code == 404
    assert client.post("/api/voice/speak", json={"text": "hi"}).status_code == 503

    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 1)
    from buddy import ratelimit
    ratelimit._hits.clear()
    assert client.post("/api/message", json={"session": sid, "text": "hello"}).status_code == 200
    assert client.post("/api/message", json={"session": sid, "text": "hello"}).status_code == 429
