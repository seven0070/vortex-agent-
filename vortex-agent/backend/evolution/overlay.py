"""
Runtime overlay for evolvable behavior.

Production source is never overwritten. The live agent loads the CURRENT overlay
from ~/.vortex/releases/. LAST_KNOWN_GOOD is never deleted when a later
generation is staged.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from paths import vortex_home

from .compiler import DEFAULT_OVERLAY, default_overlay, set_overlay as _set_compiler_overlay


def releases_dir() -> Path:
    p = vortex_home() / "releases"
    p.mkdir(parents=True, exist_ok=True)
    return p


def pointers_path() -> Path:
    return releases_dir() / "pointers.json"


def default_pointers() -> Dict[str, Any]:
    return {
        "current": None,
        "last_known_good": None,
        "canary": None,
        "stable_live_score": None,
        "updated_at": None,
    }


def load_pointers() -> Dict[str, Any]:
    path = pointers_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return {**default_pointers(), **data}
        except Exception:
            pass
    return default_pointers()


def save_pointers(data: Dict[str, Any]) -> None:
    data = dict(data)
    data["updated_at"] = datetime.now().isoformat()
    pointers_path().write_text(json.dumps(data, indent=2))


def release_path(gen: Any) -> Path:
    if isinstance(gen, str) and gen.startswith("v"):
        name = gen
    else:
        name = f"v{int(gen):03d}"
    return releases_dir() / name


class Overlay:
    def __init__(self, data: Optional[Dict[str, Any]] = None, source: str = "memory"):
        self.data = data if data is not None else default_overlay()
        self.source = source

    @property
    def generation_id(self) -> int:
        return int(self.data.get("generation_id") or 0)

    def copy(self) -> "Overlay":
        return Overlay(json.loads(json.dumps(self.data)), source=self.source)

    def enable(self, feature: str, value: Any = True) -> None:
        self.data.setdefault("compiler", {})[feature] = value

    def dump(self, path: Path) -> None:
        path.write_text(json.dumps(self.data, indent=2))

    @classmethod
    def load_file(cls, path: Path) -> "Overlay":
        return cls(json.loads(path.read_text()), source=str(path))

    @classmethod
    def genesis(cls) -> "Overlay":
        return cls(default_overlay(), source="genesis")


_active: Optional[Overlay] = None


def get_active() -> Overlay:
    global _active
    if _active is None:
        _active = load_current()
        _set_compiler_overlay(_active.data)
    return _active


def activate(overlay: Overlay) -> Overlay:
    global _active
    _active = overlay
    _set_compiler_overlay(overlay.data)
    return _active


def load_current() -> Overlay:
    ptr = load_pointers()
    current = ptr.get("current") or ptr.get("last_known_good")
    if current:
        overlay_file = release_path(current) / "overlay.json"
        if overlay_file.exists():
            return Overlay.load_file(overlay_file)
    return Overlay.genesis()


def load_last_known_good() -> Overlay:
    ptr = load_pointers()
    lkg = ptr.get("last_known_good")
    if lkg:
        overlay_file = release_path(lkg) / "overlay.json"
        if overlay_file.exists():
            return Overlay.load_file(overlay_file)
    return Overlay.genesis()


def next_generation_id(memory=None) -> int:
    existing = []
    for p in releases_dir().glob("v*"):
        if p.is_dir() and p.name[1:].isdigit():
            existing.append(int(p.name[1:]))
    mem_gen = 0
    if memory is not None:
        try:
            mem_gen = int(memory.current_generation() or 0)
        except Exception:
            mem_gen = 0
    return max(existing + [mem_gen] + [0]) + 1
