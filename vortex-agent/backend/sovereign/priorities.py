"""
Priorities — WHAT ARE MY CURRENT PRIORITIES?
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Any

class PriorityManager:
    def __init__(self, memory=None):
        self.memory = memory
        self._priorities: List[Dict[str, Any]] = [
            {"task": "Answer user correctly", "weight": 1.0, "active": True},
            {"task": "Maintain memory & graph consistency", "weight": 0.8, "active": True},
            {"task": "Self-improve only when eval doesn't regress", "weight": 0.85, "active": True},
            {"task": "Enforce governance & security", "weight": 0.9, "active": True},
            {"task": "Preserve traces for learning", "weight": 0.6, "active": True},
        ]

    def current(self) -> List[Dict[str, Any]]:
        return [p for p in self._priorities if p.get("active")]

    def set_priority(self, task: str, weight: float):
        for p in self._priorities:
            if p["task"] == task:
                p["weight"] = weight
                p["updated_at"] = datetime.now().isoformat()
                return
        self._priorities.append({"task": task, "weight": weight, "active": True, "updated_at": datetime.now().isoformat()})

    def reorder(self, task_order: List[str]):
        # reorder by list
        ordered = []
        for t in task_order:
            for p in self._priorities:
                if p["task"] == t:
                    ordered.append(p)
        # add remaining
        for p in self._priorities:
            if p not in ordered:
                ordered.append(p)
        self._priorities = ordered

    def top(self) -> Dict[str, Any]:
        act = self.current()
        if not act:
            return {}
        return max(act, key=lambda x: x["weight"])
