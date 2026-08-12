"""Vortex Agent — Phase 2 API."""
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from memory import Memory
from swarm import VortexAgent


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


app = FastAPI(title="Vortex Agent", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "healthy", "bots": len(agent.bots)}


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
    return {"response": agent.chat(req.message)}


@app.get("/api/skills")
async def skills():
    return agent.skills.list()


@app.get("/api/history")
async def history(limit: int = 50):
    return memory.get_history(limit)


@app.get("/api/stats")
async def stats():
    return memory.stats()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
