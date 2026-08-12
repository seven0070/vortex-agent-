"""
Sovereign State — WHAT STATE AM I IN? WHAT AM I ALLOWED TO CHANGE?
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List
import json
from pathlib import Path

class SovereignState:
    def __init__(self, memory=None):
        self.memory = memory
        from paths import vortex_home
        self.path = vortex_home() / "sovereign" / "state.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except:
                pass
        return {
            "mode": "operational",  # operational, learning, evolving, canary, degraded
            "health": "healthy",
            "generation": 0,
            "learnings": [],
            "protected_files": [
                "orchestrator.py",
                "orchestration/",
                "governance/policy.py",
                "sovereign/",
                "memory.py"
            ],
            "allowed_changes": [
                "lessons", "router_weights", "non-core tools", "skills", "procedural_memory"
            ],
            "restricted_changes": [
                "governance bypass", "direct production overwrite", "un-sandboxed exec"
            ],
            "created_at": datetime.now().isoformat(),
        }

    def _save(self):
        self._state["updated_at"] = datetime.now().isoformat()
        self.path.write_text(json.dumps(self._state, indent=2))

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._state)

    def set_mode(self, mode: str):
        self._state["mode"] = mode
        self._save()
        if self.memory:
            try:
                self.memory.log_event("sovereign:mode", mode)
            except:
                pass

    def set_health(self, health: str):
        self._state["health"] = health
        self._save()

    def add_learning(self, learning: str):
        self._state["learnings"].append({"text": learning, "at": datetime.now().isoformat()})
        self._state["learnings"] = self._state["learnings"][-100:]
        self._save()

    def is_protected(self, resource: str) -> bool:
        rs = resource.lower()
        for p in self._state.get("protected_files", []):
            if p.lower() in rs:
                return True
        return False

    def what_can_i_change(self) -> List[str]:
        return self._state.get("allowed_changes", [])

    def what_cant_i_change(self) -> List[str]:
        return self._state.get("restricted_changes", [])

    def update_generation(self, gen: int):
        self._state["generation"] = gen
        self._save()
