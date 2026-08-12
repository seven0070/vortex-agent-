"""
Observability — OpenTelemetry-style traces, metrics, execution telemetry
Every execution should produce trace_id, task_id, agent_id, generation_id, model, tokens, latency, tool_calls, memory_hits, errors, score, final_outcome
"""
from .tracer import VortexTracer, get_tracer
from .metrics import VortexMetrics

class Observability:
    def __init__(self, memory=None):
        self.tracer = get_tracer(memory=memory)
        self.metrics = VortexMetrics(memory=memory)
        self.memory = memory

    def trace_request(self, goal: str, **kwargs):
        return self.tracer.start_trace(goal, **kwargs)

    def record(self, *args, **kwargs):
        return self.tracer.record(*args, **kwargs)

__all__ = ["Observability", "VortexTracer", "get_tracer", "VortexMetrics"]
