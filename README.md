# 🌪️ Vortex Agent

**Autonomous multi-agent OS** — 24-seat council chamber, parallel seat workers, chief execution.

```
you ──► Mission Control UI / CLI / API
              │
              ▼
         Vortex Agent (chief)
              │
     ┌────────┴────────┐
     ▼                 ▼
 Solo mission     Agent Council (24 seats)
 plan→act→obs     brief→propose→critique→vote
                         │
                         ▼
                  Council Chamber
                  parallel seat AIAgents
                         │
                         ▼
                  Chief merge → FINAL.md
```

## Quick start

```bash
# from repo root
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Mission Control UI + API  →  http://localhost:8765
python run.py

# or
python -m vortex serve 8765
python run.py cli
python run.py doctor
```

Install as a package:

```bash
pip install -e .
vortex-agent              # UI + API
vortex-agent cli
vortex-agent doctor
```

### Optional real LLM

```bash
export OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY
# or OpenAI-compatible:
export VORTEX_API_KEY=...
export VORTEX_BASE_URL=https://api.example.com/v1
export VORTEX_MODEL=gpt-4o-mini
```

Without keys, the **offline planner** still runs full multi-step missions and chamber workers.

## What it is

| Layer | What it does |
|-------|----------------|
| **Vortex Agent chief** | Autonomous ReAct loop — plan → tool → observe → finish |
| **24-seat Council** | Project-inspired seats deliberate and vote |
| **Council Chamber** | Parallel seat workers execute with scoped toolsets |
| **Chief merge** | Combines chamber artifacts into `FINAL.md` |
| **Tools** | web, code, files, shell, memory, stego, council… |
| **Memory** | SQLite sessions + FTS5, vector recall, `MEMORY.md` |
| **Skills** | Bundled `SKILL.md` playbooks + learned skills |

## Agent Council

Twenty-four weighted seats (Prime, Zero, Buzz, Hermes, QM, Eve, Odysseus, OpenWorker, Grok, Notebook, LifeOS, Opik, DSPy, Kitesurf, Memory, Cognee, Multica, Alook, AgentOffice, OfficeCLI, OpenWork, Claw3D, AIOffice, Ruflo).

Pipeline:

**brief → propose → critique → vote → chamber (parallel seat agents) → chief merge**

Prime + Hermes hard-veto harmful goals.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness |
| `GET` | `/api/meta` | Product, tools, bots, seats |
| `POST` | `/api/missions` | Solo autonomous mission |
| `POST` | `/api/council` | `{ "goal", "auto_execute", "use_chamber", "wait?" }` |
| `GET` | `/api/council/seats` | Seat catalog |
| `GET` | `/api/missions/{id}/stream` | SSE live trace |
| `POST` | `/api/chat` | Chief chat |
| `WS` | `/ws` | Realtime event hub |
| `GET` | `/docs` | OpenAPI |

## CLI

```
/auto <goal>        solo mission
/council <goal>     deliberate → chamber → execute
/seats              list council
/missions /tools /skills
@researcher …       address a specialist bot
```

## Layout

```
vortex/
├── agent/           # AIAgent, council, chamber, memory, skills, OS
├── tools/           # self-registering tool belt
├── toolsets.py      # named presets
├── skills/          # bundled SKILL.md playbooks
├── gateway/         # FastAPI + SSE + WS
├── cli/             # interactive shell
├── frontend/        # Mission Control UI
└── __main__.py      # python -m vortex
run.py               # repo entrypoint
pyproject.toml       # installable package
```

## Workspace

`~/.vortex/` (override with `VORTEX_HOME`)

```
workspace/council/<id>/   chamber artifacts + FINAL.md
workspace/reports/        research outputs
memory/                   MEMORY.md + vectors
vortex.db                 sessions · steps · FTS5
skills/                   learned skills
```

## License

MIT © 2026 Sanath S Patil

Architecture inspired by [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) and a council of open-source agent projects — not a fork of their codebases.
