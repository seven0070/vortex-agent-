"""
Rollback to last known-good. Later generations are never deleted or overwritten.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .compiler import set_overlay
from .overlay import (
    Overlay,
    activate,
    load_last_known_good,
    load_pointers,
    release_path,
    save_pointers,
)


class RollbackManager:
    def __init__(self, agent=None, memory=None):
        self.agent = agent
        self.memory = memory or (getattr(agent, "memory", None) if agent else None)

    def rollback(self, reason: str, failed_generation: int = None) -> Dict[str, Any]:
        lkg = load_last_known_good()
        ptr = load_pointers()
        lkg_name = ptr.get("last_known_good")
        activate(lkg)
        set_overlay(lkg.data)
        ptr["current"] = lkg_name
        ptr["canary"] = None
        save_pointers(ptr)

        if failed_generation is not None:
            failed_dir = release_path(failed_generation)
            record = {
                "rolled_back_from": failed_generation,
                "restored": lkg_name,
                "reason": reason,
                "at": datetime.now().isoformat(),
            }
            try:
                (failed_dir / "rollback.json").write_text(json.dumps(record, indent=2))
                cand = failed_dir / "candidate_final.json"
                if cand.exists():
                    data = json.loads(cand.read_text())
                    data["status"] = "rolled_back"
                    data["decision"] = "rolled_back"
                    data["reason"] = reason
                    cand.write_text(json.dumps(data, indent=2))
            except Exception:
                pass

        if self.memory:
            try:
                self.memory.log_event("evolution_rollback", f"{failed_generation} → {lkg_name}: {reason}")
            except Exception:
                pass
        if self.agent and getattr(self.agent, "sovereign", None):
            try:
                self.agent.sovereign.lifecycle.mark_rollback(reason)
                self.agent.sovereign.state.set_mode("operational")
                self.agent.sovereign.state.set_health("recovered")
            except Exception:
                pass
        return {
            "action": "rollback",
            "restored": lkg_name,
            "generation": lkg.generation_id,
            "reason": reason,
            "overlay": lkg.data,
        }

    def monitor_and_maybe_rollback(self, window: int = 20, floor: float = 0.45) -> Dict[str, Any]:
        """If live scores collapse versus the stable generation, restore LKG."""
        if not self.memory:
            return {"action": "skip", "reason": "no memory"}
        traces = self.memory.get_traces(window) or []
        if len(traces) < 5:
            return {"action": "skip", "reason": "not enough traces"}
        avg = sum((t.get("score") or 0) for t in traces) / len(traces)
        ptr = load_pointers()
        current = ptr.get("current")
        lkg = ptr.get("last_known_good")
        if current and lkg and str(current) == str(lkg) and ptr.get("stable_live_score") is None:
            # single generation: still roll back to genesis overlay if scores collapse
            pass
        degrade = avg < floor
        stable = ptr.get("stable_live_score")
        if stable is not None:
            try:
                degrade = degrade or avg < float(stable) * 0.85
            except (TypeError, ValueError):
                pass
        if degrade:
            return self.rollback(
                reason=f"monitor score {avg:.3f} degraded (floor={floor}, stable={stable})",
                failed_generation=current,
            )
        return {"action": "hold", "avg_score": round(avg, 3), "stable_live_score": stable}
