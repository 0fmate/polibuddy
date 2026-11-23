"""Tests run offline: no API key, no network."""

from __future__ import annotations

import os

os.environ["BUDDY_MODE"] = "offline"

import pytest  # noqa: E402

from buddy import catalog, config, ratelimit  # noqa: E402


@pytest.fixture(autouse=True)
def temp_runtime(tmp_path, monkeypatch):
    """Each test writes sessions and logs into its own folder."""
    monkeypatch.setattr(config, "RUNTIME_DIR", tmp_path)
    ratelimit._hits.clear()


@pytest.fixture
def sine():
    return catalog.load("lim-sine", "demo")
