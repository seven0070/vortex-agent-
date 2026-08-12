"""Shared Vortex home directory. Override with VORTEX_HOME for tests."""
import os
from pathlib import Path


def vortex_home() -> Path:
    raw = os.environ.get("VORTEX_HOME")
    p = Path(raw).expanduser() if raw else (Path.home() / ".vortex")
    p.mkdir(parents=True, exist_ok=True)
    return p
