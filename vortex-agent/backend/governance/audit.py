"""
Audit Log — governance audit trail (OpenTelemetry-style + memory persisted)
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

class AuditLog:
    def __init__(self, memory=None, base_path: Optional[Path] = None):
        self.memory = memory
        from paths import vortex_home
        self.base = base_path or (vortex_home() / "governance")
        self.base.mkdir(parents=True, exist_ok=True)
        self.log_path = self.base / "audit.jsonl"

    def log(self, task: str, agent: str, action: str, decision: str, context: dict = None, reason: str = "") -> int:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task": task[:300],
            "agent": agent,
            "action": action,
            "decision": decision,
            "reason": reason,
            "context": {k: str(v)[:200] for k, v in (context or {}).items()},
        }
        # file append
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except:
            pass
        # memory event
        if self.memory:
            try:
                self.memory.log_event("governance", json.dumps(entry))
            except:
                pass
        return 1

    def recent(self, limit=20) -> List[Dict[str, Any]]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text().strip().split("\n")[-limit:]
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except:
                pass
        return list(reversed(out))

    def stats(self) -> Dict[str, Any]:
        rec = self.recent(100)
        from collections import Counter
        decisions = Counter(r.get("decision") for r in rec)
        return {"total": len(rec), "decisions": dict(decisions)}
