"""
Objectives — WHAT AM I TRYING TO ACHIEVE?
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Any
import json
from pathlib import Path

class ObjectiveManager:
    def __init__(self, memory=None):
        self.memory = memory
        from paths import vortex_home
        self.path = vortex_home() / "sovereign" / "objectives.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.objectives: List[Dict[str, Any]] = self._load()

    def _load(self):
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except:
                pass
        # default objectives
        return [
            {"id": "obj_1", "goal": "Serve user requests with correctness, reliability, evidence", "priority": 10, "active": True, "created_at": datetime.now().isoformat()},
            {"id": "obj_2", "goal": "Continuously self-improve via eval → promote only on gain", "priority": 9, "active": True, "created_at": datetime.now().isoformat()},
            {"id": "obj_3", "goal": "Maintain persistent memory graph + vector for cross-session learning", "priority": 8, "active": True, "created_at": datetime.now().isoformat()},
            {"id": "obj_4", "goal": "Enforce governance: no unapproved core file overwrites", "priority": 10, "active": True, "created_at": datetime.now().isoformat()},
        ]

    def _save(self):
        self.path.write_text(json.dumps(self.objectives, indent=2))

    def add(self, goal: str, priority: int = 5) -> Dict[str, Any]:
        import uuid
        obj = {
            "id": f"obj_{uuid.uuid4().hex[:6]}",
            "goal": goal,
            "priority": priority,
            "active": True,
            "created_at": datetime.now().isoformat(),
        }
        self.objectives.append(obj)
        self._save()
        if self.memory:
            try:
                self.memory.log_event("sovereign:objective", goal)
            except:
                pass
        return obj

    def list_active(self) -> List[Dict[str, Any]]:
        return [o for o in self.objectives if o.get("active")]

    def complete(self, obj_id: str):
        for o in self.objectives:
            if o["id"] == obj_id:
                o["active"] = False
                o["completed_at"] = datetime.now().isoformat()
        self._save()

    def top(self, n=3) -> List[Dict[str, Any]]:
        active = self.list_active()
        active.sort(key=lambda x: -x.get("priority", 0))
        return active[:n]
