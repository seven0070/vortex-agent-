"""
Tracer — OpenTelemetry Python inspired tracer for Vortex
"""
from __future__ import annotations
import uuid
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, field, asdict

@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "running"  # running, ok, error

    def finish(self, status="ok"):
        self.end_time = time.time()
        self.status = status

    def add_event(self, name: str, attrs: dict = None):
        self.events.append({"name": name, "at": datetime.now().isoformat(), "attrs": attrs or {}})

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": int((self.end_time - self.start_time)*1000) if self.end_time else None,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
        }

@dataclass
class Trace:
    trace_id: str
    root_span: Span
    spans: List[Span] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "root": self.root_span.to_dict(),
            "spans": [s.to_dict() for s in self.spans],
        }

class VortexTracer:
    def __init__(self, memory=None, base_path: Optional[Path] = None):
        self.memory = memory
        from paths import vortex_home
        self.base = base_path or (vortex_home() / "traces")
        self.base.mkdir(parents=True, exist_ok=True)
        self.active_traces: Dict[str, Trace] = {}
        self.active_spans: Dict[str, Span] = {}

    def start_trace(self, goal: str, task_id: str = None, agent_id: str = None, generation_id: int = 0, model: str = "heuristic", **kwargs) -> str:
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        span_id = f"span_{uuid.uuid4().hex[:8]}"
        root = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_id=None,
            name="vortex_run",
            start_time=time.time(),
            attributes={
                "goal": goal[:300],
                "task_id": task_id or "root",
                "agent_id": agent_id or "chief",
                "generation_id": generation_id,
                "model": model,
                **kwargs
            }
        )
        trace = Trace(trace_id=trace_id, root_span=root)
        self.active_traces[trace_id] = trace
        self.active_spans[span_id] = root
        return trace_id

    def start_span(self, trace_id: str, name: str, parent_span_id: str = None, attributes: dict = None) -> str:
        trace = self.active_traces.get(trace_id)
        if not trace:
            return ""
        span_id = f"span_{uuid.uuid4().hex[:8]}"
        parent_id = parent_span_id or trace.root_span.span_id
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_id=parent_id,
            name=name,
            start_time=time.time(),
            attributes=attributes or {}
        )
        trace.spans.append(span)
        self.active_spans[span_id] = span
        return span_id

    def record(self, trace_id: str, span_id: str, event: str = None, attributes: dict = None, error: str = None):
        span = self.active_spans.get(span_id)
        if not span:
            return
        if event:
            span.add_event(event, attributes or {})
        if attributes:
            span.attributes.update(attributes)
        if error:
            span.attributes["error"] = error[:500]
            span.status = "error"

    def finish_span(self, span_id: str, status="ok"):
        span = self.active_spans.get(span_id)
        if span:
            span.finish(status=status)

    def finish_trace(self, trace_id: str, final_outcome: str = "", score: float = 0.0, tokens: int = 0):
        trace = self.active_traces.get(trace_id)
        if not trace:
            return None
        trace.root_span.finish(status="ok")
        trace.root_span.attributes.update({
            "final_outcome": final_outcome[:500],
            "score": score,
            "tokens": tokens,
            "ended_at": datetime.now().isoformat()
        })
        # persist
        self._persist(trace)
        # log to memory
        if self.memory:
            try:
                self.memory.log_event("trace", f"{trace_id} score={score} outcome={final_outcome[:100]}")
            except:
                pass
        return trace

    def _persist(self, trace: Trace):
        try:
            p = self.base / f"{trace.trace_id}.json"
            p.write_text(json.dumps(trace.to_dict(), indent=2))
            # also append to jsonl
            jl = self.base / "traces.jsonl"
            with open(jl, "a") as f:
                f.write(json.dumps({
                    "trace_id": trace.trace_id,
                    "created_at": trace.created_at,
                    "goal": trace.root_span.attributes.get("goal", "")[:100],
                    "score": trace.root_span.attributes.get("score"),
                    "final_outcome": trace.root_span.attributes.get("final_outcome", "")[:100],
                    "duration_ms": trace.root_span.to_dict().get("duration_ms"),
                }) + "\n")
        except Exception as e:
            print(f"[tracer] persist failed: {e}")

    def list_recent(self, limit=20) -> List[Dict[str, Any]]:
        jl = self.base / "traces.jsonl"
        if not jl.exists():
            return []
        lines = jl.read_text().strip().split("\n")[-limit:]
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except:
                pass
        return list(reversed(out))

_global_tracer: Optional[VortexTracer] = None

def get_tracer(memory=None) -> VortexTracer:
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = VortexTracer(memory=memory)
    else:
        if memory and _global_tracer.memory is None:
            _global_tracer.memory = memory
    return _global_tracer
