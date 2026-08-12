"""Vortex Agent — Phase 3 API + RSI dashboard."""
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

class SpawnRequest(BaseModel):
    name: str
    role: str = "general"


memory = None
agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global memory, agent
    memory = Memory()
    agent = VortexAgent(memory)
    yield


app = FastAPI(title="Vortex Agent", version="0.3.0", lifespan=lifespan)
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
    reply = agent.chat(req.message)
    return {
        "response": reply,
        "rsi": {
            "generation": memory.current_generation(),
            "recent_avg_score": agent.rsi.status()["recent_avg_score"],
        },
    }


@app.get("/api/skills")
async def skills():
    return agent.skills.list()


@app.get("/api/history")
async def history(limit: int = 50):
    return memory.get_history(limit)


@app.get("/api/stats")
async def stats():
    return memory.stats()


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


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
