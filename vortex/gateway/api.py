"""FastAPI gateway — Mission Control API + static UI + SSE/WS (Hermes gateway spirit)."""
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

from vortex.agent.os import VortexOS
from vortex.constants import FRONTEND_DIR, NAME, VERSION, WORKSPACE


class ChatRequest(BaseModel):
    message: str


class SpawnRequest(BaseModel):
    name: str
    role: str = "general"
    toolset: str = "core"


class MissionRequest(BaseModel):
    goal: str
    max_steps: int = Field(default=12, ge=1, le=30)
    wait: bool = False


class CouncilRequest(BaseModel):
    goal: str
    seats: Optional[list] = None
    auto_execute: bool = True
    wait: bool = False
    max_rounds: int = Field(default=3, ge=1, le=5)
    use_chamber: bool = True


os_runtime: Optional[VortexOS] = None
_ws_clients: Set[WebSocket] = set()
_event_queue: Optional[asyncio.Queue] = None
_loop: Optional[asyncio.AbstractEventLoop] = None


def _on_event(event: dict):
    if _loop is None or _event_queue is None:
        return
    try:
        _loop.call_soon_threadsafe(_event_queue.put_nowait, event)
    except Exception:
        pass


async def _dispatcher():
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
    global os_runtime, _event_queue, _loop
    _loop = asyncio.get_running_loop()
    _event_queue = asyncio.Queue()
    os_runtime = VortexOS()
    os_runtime.subscribe(_on_event)
    task = asyncio.create_task(_dispatcher())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title=NAME, version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "name": NAME,
        "version": VERSION,
        "bots": len(os_runtime.bots),
        "provider": os_runtime.brain.provider,
        "tools": len(os_runtime.list_tools()),
        "missions": os_runtime.db.stats().get("sessions", 0),
        "council_seats": len(os_runtime.council.seats),
        "architecture": "vortex-agent · council-chamber",
        "chamber": True,
    }


@app.get("/api/meta")
async def meta():
    return {
        "name": NAME,
        "version": VERSION,
        "provider": os_runtime.brain.provider,
        "model": os_runtime.brain.model or "offline-planner",
        "workspace": str(WORKSPACE),
        "architecture": "vortex-agent · council-chamber",
        "tools": os_runtime.list_tools(),
        "bots": os_runtime.list_bots(),
        "skills": os_runtime.skills.list(),
        "council_seats": os_runtime.council.list_seats(),
        "chamber": True,
        "product": NAME,
    }


# ── Agent Council ──────────────────────────────────────────────────────────
@app.get("/api/council/seats")
async def council_seats():
    return os_runtime.council.list_seats()


@app.get("/api/council")
async def council_list():
    return os_runtime.council.list_sessions()


@app.post("/api/council")
async def council_convene(req: CouncilRequest):
    if not req.goal.strip():
        raise HTTPException(400, "goal required")
    if req.wait:
        result = await asyncio.to_thread(
            lambda: os_runtime.council.convene(
                req.goal,
                seat_ids=req.seats,
                auto_execute=req.auto_execute,
                background=False,
                max_rounds=req.max_rounds,
                use_chamber=req.use_chamber,
            )
        )
    else:
        result = os_runtime.council.convene(
            req.goal,
            seat_ids=req.seats,
            auto_execute=req.auto_execute,
            background=True,
            max_rounds=req.max_rounds,
            use_chamber=req.use_chamber,
        )
    return result


@app.get("/api/council/{cid}")
async def council_get(cid: str):
    s = os_runtime.council.get(cid)
    if not s:
        raise HTTPException(404, "council session not found")
    return s


@app.post("/api/council/{cid}/cancel")
async def council_cancel(cid: str):
    ok = os_runtime.council.cancel(cid)
    return {"status": "cancelling" if ok else "not_running"}


@app.get("/api/bots")
async def bots():
    return os_runtime.list_bots()


@app.post("/api/bots")
async def spawn(req: SpawnRequest):
    os_runtime.spawn_bot(req.name, req.role, req.toolset)
    return {"status": "spawned", "name": req.name, "role": req.role, "toolset": req.toolset}


@app.delete("/api/bots/{name}")
async def kill(name: str):
    return {"status": "killed" if os_runtime.kill_bot(name) else "not_found"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "message required")
    reply = await asyncio.to_thread(os_runtime.chat, req.message)
    return {"response": reply}


@app.post("/api/chat/{bot_name}")
async def chat_bot(bot_name: str, req: ChatRequest):
    if bot_name not in os_runtime.bots:
        raise HTTPException(404, f"bot '{bot_name}' not found")
    reply = await asyncio.to_thread(os_runtime.bots[bot_name].handle, req.message)
    return {"response": reply, "bot": bot_name}


@app.post("/api/missions")
async def create_mission(req: MissionRequest):
    if not req.goal.strip():
        raise HTTPException(400, "goal required")
    agent = os_runtime.agent
    if req.wait:
        mission = await asyncio.to_thread(agent.run, req.goal, False, req.max_steps)
    else:
        mission = agent.run(req.goal, background=True, max_steps=req.max_steps)
    return mission


@app.get("/api/missions")
async def list_missions():
    return os_runtime.agent.list_missions()


@app.get("/api/missions/{mid}")
async def get_mission(mid: str):
    m = os_runtime.agent.get_mission(mid)
    if not m:
        raise HTTPException(404, "mission not found")
    return m


@app.post("/api/missions/{mid}/cancel")
async def cancel_mission(mid: str):
    ok = os_runtime.agent.cancel(mid)
    return {"status": "cancelling" if ok else "not_running"}


@app.get("/api/tools")
async def list_tools():
    return os_runtime.list_tools()


@app.get("/api/skills")
async def skills():
    return os_runtime.skills.list()


@app.get("/api/history")
async def history(limit: int = 50):
    # flatten recent session messages via events/stats
    return os_runtime.db.get_events(limit)


@app.get("/api/stats")
async def stats():
    s = os_runtime.db.stats()
    s["provider"] = os_runtime.brain.provider
    s["bots"] = len(os_runtime.bots)
    s["missions"] = s.get("sessions", 0)
    s["tools"] = len(os_runtime.list_tools())
    return s


@app.get("/api/events")
async def events(limit: int = 50):
    return os_runtime.db.get_events(limit)


@app.get("/api/missions/{mid}/stream")
async def stream_mission(mid: str):
    async def gen():
        q: asyncio.Queue = asyncio.Queue()

        def handler(event: dict):
            if event.get("mission_id") == mid or event.get("session_id") == mid:
                try:
                    _loop.call_soon_threadsafe(q.put_nowait, event)
                except Exception:
                    pass

        os_runtime.subscribe(handler)
        try:
            snap = os_runtime.agent.get_mission(mid)
            if snap:
                yield f"data: {json.dumps({'type': 'snapshot', 'mission': snap})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    m = os_runtime.agent.get_mission(mid)
                    if m and m["status"] in ("completed", "failed", "cancelled"):
                        yield f"data: {json.dumps({'type': 'snapshot', 'mission': m})}\n\n"
                        break
                    continue
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") in (
                    "mission_completed",
                    "mission_failed",
                    "mission_cancelled",
                ) and (event.get("mission_id") == mid or event.get("session_id") == mid):
                    break
        finally:
            os_runtime.unsubscribe(handler)

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
                    "provider": os_runtime.brain.provider,
                    "bots": len(os_runtime.bots),
                    "architecture": "vortex-agent · council-chamber",
                    "name": NAME,
                }
            )
        )
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "cancel" and msg.get("mission_id"):
                os_runtime.agent.cancel(msg["mission_id"])
            elif msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


# Static UI — package frontend first, then legacy checkout path
_FRONTEND_CANDIDATES = [
    FRONTEND_DIR,
    Path(__file__).resolve().parent.parent / "frontend",
    Path(__file__).resolve().parent.parent.parent / "vortex-agent" / "frontend",
]
FRONTEND = next((p for p in _FRONTEND_CANDIDATES if (p / "index.html").exists()), None)

if FRONTEND:
    assets = FRONTEND / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(FRONTEND / "index.html")
else:

    @app.get("/")
    async def index():
        return HTMLResponse(
            f"<h1>🌪️ {NAME}</h1><p>v{VERSION} · autonomous multi-agent OS</p>"
            "<ul><li><a href='/health'>/health</a></li>"
            "<li><a href='/api/meta'>/api/meta</a></li>"
            "<li><a href='/docs'>/docs</a></li></ul>"
        )


def main(argv=None):
    argv = argv or sys.argv[1:]
    port = int(argv[0]) if argv else 8765
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
