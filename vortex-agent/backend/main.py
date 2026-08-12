"""Vortex Agent — Autonomous API (Phase 3)."""
from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Set

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from memory import Memory
from swarm import VortexAgent


class ChatRequest(BaseModel):
    message: str


class SpawnRequest(BaseModel):
    name: str
    role: str = "general"


class MissionRequest(BaseModel):
    goal: str
    max_steps: int = Field(default=12, ge=1, le=25)
    wait: bool = False  # if true, run sync and return final result


memory: Optional[Memory] = None
agent: Optional[VortexAgent] = None

# websocket fan-out
_ws_clients: Set[WebSocket] = set()
_event_queue: Optional[asyncio.Queue] = None
_loop: Optional[asyncio.AbstractEventLoop] = None


def _on_auto_event(event: dict):
    """Called from worker threads — schedule onto the asyncio loop."""
    global _loop, _event_queue
    if _loop is None or _event_queue is None:
        return
    try:
        _loop.call_soon_threadsafe(_event_queue.put_nowait, event)
    except Exception:
        pass


async def _event_dispatcher():
    """Broadcast autonomous events to all websocket clients."""
    assert _event_queue is not None
    while True:
        event = await _event_queue.get()
        dead = []
        payload = json.dumps(event, default=str)
        for ws in list(_ws_clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _ws_clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global memory, agent, _event_queue, _loop
    _loop = asyncio.get_running_loop()
    _event_queue = asyncio.Queue()
    memory = Memory()
    agent = VortexAgent(memory)
    agent.auto.subscribe(_on_auto_event)
    dispatcher = asyncio.create_task(_event_dispatcher())
    yield
    dispatcher.cancel()
    try:
        await dispatcher
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Vortex Agent", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── health / meta ──────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.3.0",
        "bots": len(agent.bots),
        "provider": agent.auto.brain.provider,
        "tools": len(agent.auto.tools),
        "missions": len(agent.auto.missions),
    }


@app.get("/api/meta")
async def meta():
    return {
        "name": "Vortex Agent",
        "version": "0.3.0",
        "provider": agent.auto.brain.provider,
        "model": agent.auto.brain.model or "offline-planner",
        "workspace": str(Path.home() / ".vortex" / "workspace"),
        "tools": agent.auto.list_tools(),
        "bots": agent.list_bots(),
    }


# ── swarm ──────────────────────────────────────────────────────────────────
@app.get("/api/bots")
async def bots():
    return agent.list_bots()


@app.post("/api/bots")
async def spawn(req: SpawnRequest):
    agent.spawn_bot(req.name, req.role)
    return {"status": "spawned", "name": req.name, "role": req.role}


@app.delete("/api/bots/{name}")
async def kill(name: str):
    return {"status": "killed" if agent.kill_bot(name) else "not_found"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "message required")
    # run in thread so long autonomous chat doesn't block the loop
    reply = await asyncio.to_thread(agent.chat, req.message)
    return {"response": reply}


@app.post("/api/chat/{bot_name}")
async def chat_bot(bot_name: str, req: ChatRequest):
    if bot_name not in agent.bots:
        raise HTTPException(404, f"bot '{bot_name}' not found")
    reply = await asyncio.to_thread(agent.bots[bot_name].handle, req.message)
    return {"response": reply, "bot": bot_name}


# ── autonomous missions ────────────────────────────────────────────────────
@app.post("/api/missions")
async def create_mission(req: MissionRequest):
    if not req.goal.strip():
        raise HTTPException(400, "goal required")
    if req.wait:
        mission = await asyncio.to_thread(
            agent.auto.run_sync, req.goal, req.max_steps
        )
    else:
        mission = agent.auto.start_mission(req.goal, max_steps=req.max_steps)
    return mission


@app.get("/api/missions")
async def list_missions():
    return agent.auto.list_missions()


@app.get("/api/missions/{mid}")
async def get_mission(mid: str):
    m = agent.auto.get_mission(mid)
    if not m:
        raise HTTPException(404, "mission not found")
    return m


@app.post("/api/missions/{mid}/cancel")
async def cancel_mission(mid: str):
    ok = agent.auto.cancel(mid)
    return {"status": "cancelling" if ok else "not_running"}


@app.get("/api/tools")
async def list_tools():
    return agent.auto.list_tools()


@app.get("/api/skills")
async def skills():
    return agent.skills.list()


@app.get("/api/history")
async def history(limit: int = 50):
    return memory.get_history(limit)


@app.get("/api/stats")
async def stats():
    s = memory.stats()
    s["provider"] = agent.auto.brain.provider
    s["bots"] = len(agent.bots)
    s["missions"] = len(agent.auto.missions)
    s["tools"] = len(agent.auto.tools)
    return s


@app.get("/api/events")
async def events(limit: int = 50):
    return memory.get_events(limit)


# ── live streams ───────────────────────────────────────────────────────────
@app.get("/api/missions/{mid}/stream")
async def stream_mission(mid: str):
    """Server-Sent Events for a single mission."""

    async def gen():
        q: asyncio.Queue = asyncio.Queue()

        def handler(event: dict):
            if event.get("mission_id") == mid or event.get("type", "").startswith(
                "mission_"
            ):
                try:
                    _loop.call_soon_threadsafe(q.put_nowait, event)
                except Exception:
                    pass

        agent.auto.subscribe(handler)
        try:
            # push current snapshot first
            snap = agent.auto.get_mission(mid)
            if snap:
                yield f"data: {json.dumps({'type': 'snapshot', 'mission': snap})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    m = agent.auto.get_mission(mid)
                    if m and m["status"] in (
                        "completed",
                        "failed",
                        "cancelled",
                    ):
                        yield f"data: {json.dumps({'type': 'snapshot', 'mission': m})}\n\n"
                        break
                    continue
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") in (
                    "mission_completed",
                    "mission_failed",
                    "mission_cancelled",
                ) and event.get("mission_id") == mid:
                    break
        finally:
            agent.auto.unsubscribe(handler)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.websocket("/ws")
async def ws_hub(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        await ws.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "provider": agent.auto.brain.provider,
                    "bots": len(agent.bots),
                }
            )
        )
        while True:
            # keep alive; client messages optional (cancel etc.)
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "cancel" and msg.get("mission_id"):
                agent.auto.cancel(msg["mission_id"])
            elif msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


# ── static frontend ────────────────────────────────────────────────────────
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND.exists():
    assets = FRONTEND / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/")
    async def index():
        index_path = FRONTEND / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return HTMLResponse("<h1>Vortex Agent API</h1><p>Frontend missing.</p>")

else:

    @app.get("/")
    async def index():
        return HTMLResponse(
            "<h1>🌪️ Vortex Agent API</h1>"
            "<p>API is live. Drop a frontend into <code>vortex-agent/frontend</code>.</p>"
            "<ul>"
            "<li><a href='/health'>/health</a></li>"
            "<li><a href='/api/meta'>/api/meta</a></li>"
            "<li><a href='/docs'>/docs</a></li>"
            "</ul>"
        )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    # 0.0.0.0 so the Arena preview proxy can reach us
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
