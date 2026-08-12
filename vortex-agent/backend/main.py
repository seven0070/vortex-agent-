"""Vortex Agent — Phase 4 API + RSI + Council + Sovereign + Governance + Observability + Orchestration dashboard."""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from memory import Memory
from swarm import VortexAgent

STATIC = Path(__file__).resolve().parent / "static"

class ChatRequest(BaseModel):
    message: str
    orchestrated: bool = False  # if true, use full graph path

class SpawnRequest(BaseModel):
    name: str
    role: str = "general"

class ResolveRequest(BaseModel):
    goal: str = ""
    candidates: list = []

memory = None
agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global memory, agent
    memory = Memory()
    agent = VortexAgent(memory)
    yield

app = FastAPI(title="Vortex Agent", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "bots": len(agent.bots),
        "generation": memory.current_generation(),
        "lessons": len(memory.get_lessons(True)),
        "council_members": list(agent.council.members.keys()) if agent.council else [],
        "governance_policies": len(agent.governance.policy.policies) if agent.governance else 0,
        "sovereign_mode": agent.sovereign.state.snapshot().get("mode") if agent.sovereign else "unknown",
    }

@app.get("/api/bots")
async def bots():
    return agent.list_bots()

@app.post("/api/bots")
async def spawn(req: SpawnRequest):
    agent.spawn_bot(req.name, req.role)
    return {"status": "spawned"}

@app.delete("/api/bots/{name}")
async def kill(name: str):
    return {"status": "killed" if agent.kill_bot(name) else "not_found"}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if req.orchestrated and agent.graph:
        reply = agent.run_orchestrated(req.message, original_message=req.message)
    else:
        reply = agent.chat(req.message)
    return {
        "response": reply,
        "rsi": {
            "generation": memory.current_generation(),
            "recent_avg_score": agent.rsi.status()["recent_avg_score"],
        },
        "orchestrated": req.orchestrated,
    }

@app.post("/api/chat/orchestrated")
async def chat_orchestrated(req: ChatRequest):
    reply = agent.run_orchestrated(req.message, original_message=req.message)
    return {"response": reply, "orchestrated": True, "state": agent.state_manager.list_recent(1)[0].to_dict() if agent.state_manager and agent.state_manager.list_recent(1) else {}}

@app.get("/api/skills")
async def skills():
    return agent.skills.list()

@app.get("/api/history")
async def history(limit: int = 50):
    return memory.get_history(limit)

@app.get("/api/stats")
async def stats():
    base = memory.stats()
    extra = {}
    try:
        if agent.council:
            extra["council"] = agent.council.stats()
        if agent.governance:
            extra["governance"] = agent.governance.audit.stats()
        if agent.sovereign:
            extra["sovereign"] = agent.sovereign.context()
        if agent.observability:
            extra["metrics"] = agent.observability.metrics.summary()
            extra["traces"] = agent.observability.tracer.list_recent(5)
        if hasattr(memory, 'graph') and memory.graph:
            extra["knowledge_graph"] = memory.graph.stats()
        if agent.tool_registry:
            extra["tools"] = agent.tool_registry.categories()
    except Exception as e:
        extra["stats_error"] = str(e)[:200]
    return {**base, **extra}

@app.get("/api/rsi")
async def rsi_status():
    return agent.rsi.status()

@app.get("/api/rsi/traces")
async def rsi_traces(limit: int = 40):
    return memory.get_traces(limit)

@app.get("/api/rsi/lessons")
async def rsi_lessons():
    return memory.get_lessons(True)

@app.get("/api/rsi/generations")
async def rsi_generations():
    return memory.get_generations(30)

@app.get("/api/rsi/evals")
async def rsi_evals():
    return memory.get_evals(20)

@app.post("/api/rsi/cycle")
async def rsi_cycle():
    return agent.rsi.run_cycle()

@app.post("/api/rsi/eval")
async def rsi_eval():
    from evals import run_suite
    return run_suite(agent, name="api")

@app.post("/api/rsi/eval/benchmark")
async def rsi_benchmark():
    from evals import VortexBenchmark
    vb = VortexBenchmark(agent)
    result = vb.run_comprehensive(persist=True)
    return result

@app.post("/api/rsi/evolve")
async def rsi_evolve():
    return agent.rsi.evolution.evolve_once()

@app.get("/api/rsi/releases")
async def rsi_releases():
    return agent.rsi.evolution.status()

@app.post("/api/rsi/rollback")
async def rsi_rollback(payload: dict = None):
    payload = payload or {}
    return agent.rsi.evolution.rollback.rollback(
        reason=payload.get("reason", "manual rollback"),
        failed_generation=payload.get("generation"),
    )

@app.get("/api/memory")
async def memory_full(query: str = "", limit: int = 10):
    if query:
        recall = memory.recall(query, n=limit)
        return {"query": query, "recall": recall}
    return {
        "stats": memory.stats(),
        "working": memory.working.get_context(5),
        "graph": memory.graph.stats() if hasattr(memory, 'graph') and memory.graph else {},
        "recent_history": memory.get_history(10),
    }

@app.post("/api/memory/remember")
async def memory_remember(payload: dict):
    text = payload.get("text", "")
    kind = payload.get("kind", "fact")
    res = memory.remember(text, kind=kind, meta=payload.get("meta", {}))
    return res

@app.get("/api/memory/graph")
async def memory_graph(limit: int = 20):
    if hasattr(memory, 'graph') and memory.graph:
        return {"nodes": memory.graph.get_all(limit), "stats": memory.graph.stats()}
    return {"nodes": [], "stats": {}}

@app.get("/api/council")
async def council_status():
    if not agent.council:
        return {"error": "council not loaded"}
    return {"members": list(agent.council.members.keys()), "weights": agent.council.weights, "stats": agent.council.stats()}

@app.post("/api/council/deliberate")
async def council_deliberate(req: ChatRequest):
    if not agent.council:
        return {"error": "council not loaded"}
    return agent.council.deliberate(goal=req.message)

@app.get("/api/governance")
async def governance_status():
    if not agent.governance:
        return {"error": "governance not loaded"}
    return {
        "policies": agent.governance.policy.list_policies(),
        "audit_recent": agent.governance.audit.recent(10),
        "stats": agent.governance.audit.stats(),
    }

@app.post("/api/governance/evaluate")
async def governance_evaluate(payload: dict):
    task = payload.get("task", "")
    context = payload.get("context", {})
    agent_name = payload.get("agent", "chief")
    action = payload.get("action", "execute")
    if not agent.governance:
        return {"error": "governance not loaded"}
    return agent.governance.evaluate(task=task, context=context, agent=agent_name, action=action)

@app.get("/api/sovereign")
async def sovereign_status():
    if not agent.sovereign:
        return {"error": "sovereign not loaded"}
    return agent.sovereign.context()

@app.get("/api/tools")
async def tools_list():
    if not agent.tool_registry:
        return {"error": "tool registry not loaded"}
    return {"tools": agent.tool_registry.list(), "categories": agent.tool_registry.categories()}

@app.post("/api/tools/exec")
async def tools_exec(payload: dict):
    name = payload.get("name")
    args = payload.get("args", {})
    agent_name = payload.get("agent", "chief")
    if not agent.tool_registry:
        return {"error": "tool registry not loaded"}
    result = agent.tool_registry.execute(name, agent=agent_name, **args)
    return result.to_dict()

@app.get("/api/orchestration")
async def orch_list():
    if not agent.state_manager:
        return {"error": "state manager not loaded"}
    recents = agent.state_manager.list_recent(10)
    return [r.to_dict() for r in recents]

@app.post("/api/orchestration/run")
async def orch_run(req: ChatRequest):
    if not agent.graph:
        return {"error": "graph not loaded"}
    state = agent.graph.run(goal=req.message, original_message=req.message, generation=memory.current_generation())
    return state.to_dict()

@app.get("/api/observability")
async def observability_status():
    if not agent.observability:
        return {"error": "observability not loaded"}
    return {
        "metrics": agent.observability.metrics.summary(),
        "traces": agent.observability.tracer.list_recent(10),
    }

@app.post("/api/resolution/resolve")
async def resolution_resolve(req: ResolveRequest):
    if not agent.resolver:
        return {"error": "resolver not loaded"}
    # if no candidates provided, use recent task results
    candidates = req.candidates or [{"result": f"candidate {i}", "confidence": 0.6} for i in range(2)]
    return agent.resolver.resolve(candidates, goal=req.goal)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
