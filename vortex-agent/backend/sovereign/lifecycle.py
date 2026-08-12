"""
Lifecycle — manage born → operational → canary → deploy → monitor → rollback (for self-improvement)
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List
import json
from pathlib import Path

class LifecycleManager:
    def __init__(self, memory=None):
        self.memory = memory
        from paths import vortex_home
        self.base = vortex_home() / "sovereign" / "lifecycle"
        self.base.mkdir(parents=True, exist_ok=True)
        self.state_path = self.base / "lifecycle.json"
        self._state = self._load()

    def _load(self):
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except:
                pass
        return {
            "phase": "born",
            "history": [],
            "rollbacks": 0,
            "deploys": 0,
            "canary_active": False,
            "created_at": datetime.now().isoformat(),
        }

    def _save(self):
        self.state_path.write_text(json.dumps(self._state, indent=2))

    def transition(self, new_phase: str, note: str = ""):
        prev = self._state["phase"]
        self._state["phase"] = new_phase
        self._state["history"].append({
            "from": prev,
            "to": new_phase,
            "note": note,
            "at": datetime.now().isoformat()
        })
        self._state["history"] = self._state["history"][-50:]
        self._save()
        if self.memory:
            try:
                self.memory.log_event("sovereign:lifecycle", f"{prev}->{new_phase}: {note}")
            except:
                pass

    def status(self) -> Dict[str, Any]:
        return dict(self._state)

    def mark_deploy(self, generation: int):
        self._state["deploys"] += 1
        self.transition("deployed", f"gen {generation}")

    def mark_rollback(self, reason: str):
        self._state["rollbacks"] += 1
        self.transition("rolled_back", reason)

    def start_canary(self, generation: int):
        self._state["canary_active"] = True
        self.transition("canary", f"gen {generation} canary start")

    def end_canary(self, success: bool):
        self._state["canary_active"] = False
        if success:
            self.transition("canary_passed", "canary success")
        else:
            self.transition("canary_failed", "canary failed")
