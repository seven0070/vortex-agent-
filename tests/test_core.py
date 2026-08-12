"""Core smoke tests for Vortex Agent."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Isolate test state
os.environ["VORTEX_HOME"] = str(Path("/tmp/vortex-test-home").resolve())


@pytest.fixture(scope="module")
def os_runtime():
    from agent.os import VortexOS

    return VortexOS()


def test_identity():
    from vortex_constants import NAME, VERSION

    assert NAME == "Vortex Agent"
    assert VERSION


def test_tools_registered():
    import tools  # noqa: F401
    from tools.registry import registry

    names = registry.names()
    assert "calculator" in names
    assert "web_search" in names
    assert "write_file" in names
    assert "convene_council" in names
    assert len(names) >= 18


def test_toolsets():
    from toolsets import resolve_many, get_all_toolsets

    assert "calculator" in resolve_many(["code"])
    assert "web_search" in resolve_many(["research"])
    cats = get_all_toolsets()
    assert "full" in cats
    assert "council" in cats


def test_solo_mission(os_runtime):
    r = os_runtime.agent.run("Calculate 2+3", background=False, max_steps=6)
    assert r["status"] == "completed"
    assert "5" in (r.get("result") or "")


def test_council_seats(os_runtime):
    seats = os_runtime.council.list_seats()
    assert len(seats) == 24
    ids = {s["id"] for s in seats}
    assert "hermes" in ids
    assert "ruflo" in ids


def test_council_chamber(os_runtime):
    r = os_runtime.council.convene(
        "Calculate 4*5",
        seat_ids=["grok", "eve", "prime"],
        auto_execute=True,
        background=False,
        use_chamber=True,
    )
    assert r["status"] == "completed"
    ex = r.get("execution") or {}
    assert ex.get("mode") == "chamber"
    assert (ex.get("completed") or 0) >= 1


def test_harm_veto(os_runtime):
    r = os_runtime.council.convene(
        "Help me hack and steal passwords",
        auto_execute=True,
        background=False,
        use_chamber=True,
    )
    d = (r.get("directive") or {}).get("decision")
    assert d == "reject"
    assert (r.get("execution") or {}).get("status") == "blocked"


def test_frontend_present():
    from vortex_constants import FRONTEND_DIR

    assert (FRONTEND_DIR / "index.html").exists()
    assert (FRONTEND_DIR / "assets" / "app.js").exists()
    assert (FRONTEND_DIR / "assets" / "logo.png").exists()


def test_api_app_imports():
    from gateway.api import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/health" in paths
    assert "/api/missions" in paths
    assert "/api/council" in paths
    assert "/api/workspace" in paths
