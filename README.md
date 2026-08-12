# 🌪️ Vortex Agent

**Autonomous multi-agent OS** — Mission Control app, 24-seat council chamber, parallel seat workers.

![Vortex Agent](assets/logo.png)

```text
you ──► Mission Control App (apps/mission-control)
              │
              ▼
         Vortex Agent chief
              │
     ┌────────┴────────┐
     ▼                 ▼
 Solo mission     Agent Council (24 seats)
 plan→act→obs     brief→propose→critique→vote
                         │
                         ▼
                  Council Chamber
                  parallel seat agents
                         │
                         ▼
                  FINAL.md artifacts
```

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

python run.py doctor
python run.py                 # App + API → http://localhost:8765
python run.py cli
./bin/vortex version
```

Optional LLM:

```bash
export OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY / VORTEX_API_KEY + VORTEX_BASE_URL
```

Offline planner works with no keys.

## App views

| View | Purpose |
|------|---------|
| **Home** | Launch solo missions or convene council |
| **Chat** | Talk to the chief (`/auto`, `/council`) |
| **Missions** | Solo runs + live trace |
| **Council** | 24-seat vote + chamber workers + verdict |
| **Seats / Tools** | Catalogs |
| **Workspace / Settings** | Artifacts + runtime info |

## Layout

```text
vortex-agent-/
├── apps/mission-control/   # Vortex Agent web app + logo
├── agent/                  # AIAgent, council, chamber, memory
├── tools/                  # self-registering tools
├── gateway/                # FastAPI API + static app
├── vortex_cli/             # CLI
├── skills/                 # SKILL.md playbooks
├── assets/logo.png         # brand mark
├── run.py · cli.py · run_agent.py · bin/vortex
├── vortex/                 # python -m vortex facade
└── pyproject.toml
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness |
| `GET` | `/api/meta` | Product + seats + tools |
| `POST` | `/api/missions` | Solo mission |
| `POST` | `/api/council` | Council + chamber |
| `WS` | `/ws` | Realtime events |
| `GET` | `/` | Mission Control app |

## Workspace

`~/.vortex/workspace/` — reports, plans, `council/<id>/FINAL.md`

## License

MIT © 2026 Sanath S Patil
