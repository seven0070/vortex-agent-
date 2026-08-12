# 🌪️ Vortex Agent

**Autonomous multi-agent OS** — Hermes-style layout, 24-seat council chamber, parallel seat workers.

External structure is modeled on [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent).

```text
┌─────────────────────────────────────────────────────────────┐
│  Entry points                                                │
│  cli.py · run.py · gateway/ · apps/mission-control           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  AIAgent  (run_agent.py + agent/)                            │
│  prompt · provider · tool dispatch · council · chamber       │
└──────────────┬───────────────────────────┬──────────────────┘
               ▼                           ▼
     SessionDB + memory              tools/ + toolsets.py
     skills/                         gateway/ · plugins/
```

## Layout (Hermes-aligned)

| Hermes | Vortex Agent |
|--------|----------------|
| `run_agent.py` | `run_agent.py` |
| `cli.py` | `cli.py` |
| `agent/` | `agent/` |
| `tools/` | `tools/` |
| `toolsets.py` | `toolsets.py` |
| `model_tools.py` | `model_tools.py` |
| `gateway/` | `gateway/` |
| `hermes_cli/` | `vortex_cli/` |
| `skills/` | `skills/` |
| `cron/` | `cron/` |
| `plugins/` | `plugins/` |
| `apps/` | `apps/mission-control/` |
| `hermes` binary | `bin/vortex` |
| `hermes_constants.py` | `vortex_constants.py` |

```text
vortex-agent-/
├── agent/                 # core: AIAgent, council, chamber, memory
├── tools/                 # self-registering tool belt
├── toolsets.py
├── model_tools.py
├── gateway/               # FastAPI Mission Control API
├── vortex_cli/            # CLI implementation
├── skills/                # SKILL.md playbooks
├── cron/ plugins/ apps/
├── run_agent.py cli.py run.py
├── vortex_constants.py utils.py
├── bin/vortex
├── vortex/                # python -m vortex facade
└── pyproject.toml
```

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

python run.py doctor
python run.py                 # http://localhost:8765
python run.py cli
python run_agent.py "Calculate 2+2"
python run_agent.py --council "Research X and write a report"
./bin/vortex version
```

### Optional LLM

```bash
export OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY / VORTEX_API_KEY + VORTEX_BASE_URL
```

Offline planner works with no keys.

## Runtime features

- **Autonomous chief** — plan → act → observe
- **24-seat Agent Council** — project-inspired personas vote
- **Council Chamber** — parallel seat `AIAgent` workers write artifacts
- **Chief merge** — `~/.vortex/workspace/council/<id>/FINAL.md`
- **Tools** — web, code, files, shell, memory, stego, council…
- **Skills** — bundled + learned `SKILL.md` / JSON skills
- **Mission Control UI** — live thought/tool/chamber trace

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness |
| `GET` | `/api/meta` | Product + seats + tools |
| `POST` | `/api/missions` | Solo mission |
| `POST` | `/api/council` | Council + chamber |
| `WS` | `/ws` | Realtime events |
| `GET` | `/docs` | OpenAPI |

## Workspace

`~/.vortex/` (`VORTEX_HOME` override)

```text
workspace/council/<id>/   chamber outputs + FINAL.md
workspace/reports/
memory/
vortex.db
skills/
```

## License

MIT © 2026 Sanath S Patil

Layout and architecture patterns inspired by [Hermes Agent](https://github.com/NousResearch/hermes-agent) — not a fork of the Hermes codebase.
