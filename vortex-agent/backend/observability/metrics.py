"""
Metrics — counters, histograms, gauges for Vortex
"""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Dict, Any, List
from datetime import datetime
import json
from pathlib import Path

class VortexMetrics:
    def __init__(self, memory=None, base_path=None):
        self.memory = memory
        from paths import vortex_home
        self.base = base_path or (vortex_home() / "metrics")
        self.base.mkdir(parents=True, exist_ok=True)
        self.counters: Counter = Counter()
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.gauges: Dict[str, float] = {}
        self._load()

    def _load(self):
        p = self.base / "metrics.json"
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self.counters = Counter(data.get("counters", {}))
                self.gauges = data.get("gauges", {})
            except:
                pass

    def _save(self):
        p = self.base / "metrics.json"
        try:
            p.write_text(json.dumps({
                "counters": dict(self.counters),
                "gauges": self.gauges,
                "updated_at": datetime.now().isoformat(),
            }, indent=2))
        except:
            pass

    def inc(self, name: str, value: int = 1, tags: dict = None):
        self.counters[name] += value
        self._save()

    def observe(self, name: str, value: float):
        self.histograms[name].append(value)
        self.histograms[name] = self.histograms[name][-500:]
        self.gauges[f"{name}_avg"] = sum(self.histograms[name]) / len(self.histograms[name]) if self.histograms[name] else 0

    def gauge(self, name: str, value: float):
        self.gauges[name] = value
        self._save()

    def record_tool_call(self, tool: str, status: str, latency_ms: int):
        self.inc(f"tool_{tool}_{status}")
        self.observe(f"tool_{tool}_latency", latency_ms)
        self.inc("tool_calls_total")

    def record_memory_hit(self, kind: str):
        self.inc(f"memory_{kind}_hit")

    def record_council(self, decision: str):
        self.inc(f"council_{decision}")

    def record_resolution(self, selected: bool, score: float):
        self.inc("resolution_total")
        if selected:
            self.inc("resolution_selected")
        self.observe("resolution_score", score)

    def summary(self) -> Dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "gauges": self.gauges,
            "histograms": {k: {"count": len(v), "avg": sum(v)/len(v) if v else 0, "min": min(v) if v else 0, "max": max(v) if v else 0} for k, v in self.histograms.items()}
        }
