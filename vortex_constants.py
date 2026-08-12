"""Vortex Agent paths and identity (Hermes-style root constants module)."""
from __future__ import annotations

import os
from pathlib import Path

NAME = "Vortex Agent"
VERSION = "2.2.1"
TAGLINE = "Autonomous multi-agent OS · Hermes layout · 24-seat council chamber"

# Repo root (this file lives at repository root)
REPO_ROOT = Path(__file__).resolve().parent

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

# Bundled assets at Hermes-style top level
BUNDLED_SKILLS = REPO_ROOT / "skills"
FRONTEND_DIR = REPO_ROOT / "apps" / "mission-control"
# Back-compat alias
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
