"""Vortex Agent paths and identity (Hermes-style root constants module)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

NAME = "Vortex Agent"
VERSION = "2.3.0"
TAGLINE = "Autonomous multi-agent OS · 24-seat council chamber"

# Repo root when running from a checkout; fall back to package location when installed.
def _detect_repo_root() -> Path:
    here = Path(__file__).resolve().parent
    if (here / "apps" / "mission-control" / "index.html").exists():
        return here
    # installed wheel / editable: try site-packages sibling data
    for p in sys.path:
        cand = Path(p)
        if (cand / "apps" / "mission-control" / "index.html").exists():
            return cand
        if (cand / "vortex_agent_data" / "apps" / "mission-control" / "index.html").exists():
            return cand / "vortex_agent_data"
    return here


REPO_ROOT = _detect_repo_root()

VORTEX_HOME = Path(os.environ.get("VORTEX_HOME", Path.home() / ".vortex")).expanduser()
WORKSPACE = VORTEX_HOME / "workspace"
SESSIONS_DIR = VORTEX_HOME / "sessions"
SKILLS_DIR = VORTEX_HOME / "skills"
MEMORY_DIR = VORTEX_HOME / "memory"
CACHE_DIR = VORTEX_HOME / "cache"
CRON_DIR = VORTEX_HOME / "cron"
PLUGINS_DIR = VORTEX_HOME / "plugins"
STATE_DB = VORTEX_HOME / "vortex.db"
CONFIG_PATH = VORTEX_HOME / "config.yaml"
ENV_PATH = VORTEX_HOME / ".env"

BUNDLED_SKILLS = REPO_ROOT / "skills"
FRONTEND_DIR = REPO_ROOT / "apps" / "mission-control"
# Also support packaged data under vortex/data
if not (FRONTEND_DIR / "index.html").exists():
    _pkg_front = Path(__file__).resolve().parent / "vortex" / "data" / "mission-control"
    if (_pkg_front / "index.html").exists():
        FRONTEND_DIR = _pkg_front
    _pkg_skills = Path(__file__).resolve().parent / "vortex" / "data" / "skills"
    if _pkg_skills.exists():
        BUNDLED_SKILLS = _pkg_skills

PACKAGE_ROOT = REPO_ROOT


def ensure_home() -> Path:
    for p in (
        VORTEX_HOME,
        WORKSPACE,
        SESSIONS_DIR,
        SKILLS_DIR,
        MEMORY_DIR,
        CACHE_DIR,
        CRON_DIR,
        PLUGINS_DIR,
        WORKSPACE / "council",
        WORKSPACE / "reports",
        WORKSPACE / "plans",
        WORKSPACE / "knowledge",
    ):
        p.mkdir(parents=True, exist_ok=True)
    return VORTEX_HOME
