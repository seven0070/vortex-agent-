"""Vortex paths and identity — Hermes-style HERMES_HOME pattern."""
from __future__ import annotations

import os
from pathlib import Path

NAME = "Vortex"
VERSION = "1.0.0"
TAGLINE = "The autonomous agent that grows with you"

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

# Bundled skills ship with the package
PACKAGE_ROOT = Path(__file__).resolve().parent
BUNDLED_SKILLS = PACKAGE_ROOT / "skills"


def ensure_home() -> Path:
    for p in (VORTEX_HOME, WORKSPACE, SESSIONS_DIR, SKILLS_DIR, MEMORY_DIR, CACHE_DIR, CRON_DIR, PLUGINS_DIR):
        p.mkdir(parents=True, exist_ok=True)
    return VORTEX_HOME
