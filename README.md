# 🌪️ Vortex Agent

**Autonomous multi-agent OS** — give it a goal, watch it plan → act → observe until the job is done.

```
you ──► Mission Control UI / CLI / API
              │
              ▼
         Vortex Chief  ──► Autonomous ReAct loop
              │                    │
     researcher · architect   tools: search, code,
     cipher · scout           files, shell, stego…
              │                    │
              └──── memory + skills + vector store ────┘
```

## Features

- **Autonomous missions** — goal-driven loop with live thought / tool / observation trace
- **Swarm of specialist bots** — chief, researcher, architect, cipher, scout
- **Tool belt** — web search, HTTP fetch, sandboxed Python, calculator, workspace files, restricted shell, steganography, conlang, memory
- **Brain** — OpenAI / Anthropic when keyed; capable **offline planner** otherwise (no key required)
- **Persistent memory** — SQLite history + vector recall (Chroma or local TF-IDF fallback)
- **Live UI** — Mission Control dashboard with WebSocket + SSE streaming
- **Skills & bugs** — successful multi-step runs become shared skills; tool failures become patterns

## Quick start

```bash
cd vortex-agent/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# API + Mission Control UI  (http://localhost:8765)
python main.py 8765

# or interactive CLI
python cli.py
```

### Optional: real LLM

```bash
export OPENAI_API_KEY=sk-...
# or
export ANTHROPIC_API_KEY=sk-ant-...
# or any OpenAI-compatible endpoint
export VORTEX_API_KEY=...
export VORTEX_BASE_URL=https://api.example.com/v1
export VORTEX_MODEL=gpt-4o-mini
```

Without keys the offline planner still runs full multi-step missions (research, code, files, stego, etc.).

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness + bot/tool counts |
| `GET` | `/api/meta` | Provider, tools, bots |
| `POST` | `/api/missions` | `{ "goal": "...", "max_steps": 12 }` → start mission |
| `GET` | `/api/missions` | List missions |
| `GET` | `/api/missions/{id}` | Mission detail + steps |
| `GET` | `/api/missions/{id}/stream` | SSE live trace |
| `POST` | `/api/missions/{id}/cancel` | Cancel running mission |
| `POST` | `/api/chat` | Talk to chief (may auto-launch mission) |
| `GET` | `/api/tools` | Tool catalog |
| `WS` | `/ws` | Realtime event hub |

## CLI cheatsheet

```
/auto <goal>     launch autonomous mission with live trace
/missions        list missions
/tools           list tools
@researcher …    address a bot directly
/bots /spawn /kill /skills /history /stats
```

## Workspace

Artifacts land in `~/.vortex/workspace/` (reports, plans, code runs).  
Memory DB: `~/.vortex/memory.db`.

## Architecture

| Module | Role |
|--------|------|
| `autonomous.py` | Mission runner — ReAct loop, events, cancellation |
| `llm.py` | Multi-provider brain + offline planner |
| `tools.py` | Full tool belt (sandboxed) |
| `swarm.py` | Bots + chief orchestration |
| `memory.py` / `vector_memory.py` | Persistence + recall |
| `skills.py` | Shared skills & bug patterns |
| `main.py` | FastAPI + SSE + WebSocket + static UI |
| `frontend/` | Mission Control dashboard |

## License

MIT © 2026 Sanath S Patil
