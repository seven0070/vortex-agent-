"""
Identity — WHO AM I?
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any
import json
from pathlib import Path

class IdentityManager:
    def __init__(self, memory=None):
        self.memory = memory
        from paths import vortex_home
        self.path = vortex_home() / "sovereign" / "identity.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._identity = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except:
                pass
        return {
            "name": "Vortex",
            "version": "0.5.0",
            "role": "Ultron-style self-improving swarm agent",
            "principles": [
                "observe → rescue → reflect → mutate → eval → promote",
                "improvement is earned, not assumed",
                "governance has actual power",
                "resolution decides, not last agent",
                "memory is persistent graph+vector",
                "never directly overwrite production without canary"
            ],
            "created_at": datetime.now().isoformat(),
        }

    def save(self):
        self.path.write_text(json.dumps(self._identity, indent=2))

    def describe(self) -> Dict[str, Any]:
        return dict(self._identity)

    def update(self, key: str, value: Any):
        self._identity[key] = value
        self._identity["updated_at"] = datetime.now().isoformat()
        self.save()
        if self.memory:
            try:
                self.memory.log_event("sovereign:identity", f"{key}={value}")
            except:
                pass

    def whoami(self) -> str:
        return f"{self._identity.get('name')} v{self._identity.get('version')} — {self._identity.get('role')}"
