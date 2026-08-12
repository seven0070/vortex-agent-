# 🌪️ Vortex Agent

**The autonomous agent that grows with you.**

Vortex is a [Hermes Agent](https://github.com/NousResearch/hermes-agent)-inspired autonomous multi-agent OS: a narrow core waist, capability at the edges (tools · skills · swarm), and a closed learning loop.

```
┌─────────────────────────────────────────────────────────────┐
│  Entry points                                                │
│  CLI (vortex/cli) · API Gateway · Mission Control UI         │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  AIAgent  (vortex/agent/run_agent.py)                        │
│  prompt builder · provider resolution · tool dispatch        │
│  ReAct loop · context · skills · memory                      │
└──────────────┬───────────────────────────┬──────────────────┘
               ▼                           ▼
     SessionDB + FTS5              Tool Registry (self-registering)
     Vector + MEMORY.md            toolsets · delegate_task
     Skill hub (SKILL.md)          web · files · code · shell · crypto
```

Architecture borrowed from [Nous Research Hermes](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture):

| Hermes concept | Vortex module |
|----------------|---------------|
| `AIAgent` / `run_agent.py` | `vortex/agent/run_agent.py` |
| `tools/registry.py` self-register | `vortex/tools/registry.py` + tool modules |
| `toolsets.py` | `vortex/toolsets.py` |
| Skills (`SKILL.md`) | `vortex/skills/**/SKILL.md` + `SkillHub` |
| Memory provider ABC | `vortex/agent/memory_provider.py` |
| Session DB + FTS5 | `vortex/agent/state.py` |
| `delegate_task` subagents | `vortex/tools/delegate_tool.py` |
| Gateway | `vortex/gateway/api.py` |
| Prompt tiers | `vortex/agent/prompt_builder.py` |

## Quick start

```bash
pip install -r requirements.txt

# Mission Control UI + API  →  http://localhost:8765
python run.py 8765

# Interactive CLI
python run.py cli
```

Legacy shims still work: `python vortex-agent/backend/main.py`.

### Optional real LLM

```bash
export OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY / VORTEX_API_KEY + VORTEX_BASE_URL
```

Without keys, the **offline planner** still runs full multi-step missions.

## What it does

- **Autonomous missions** — goal in, plan → act → observe until done
- **Live trace** — WebSocket + SSE thought/tool/observation stream
- **Swarm** — chief · researcher · architect · cipher · scout (role toolsets)
- **Skills** — bundled `SKILL.md` playbooks + auto-learned skills from successful runs
- **Memory** — SQLite sessions, FTS5 search, vector recall, `MEMORY.md`
- **Delegation** — `delegate_task` spawns isolated child agents
- **Tool belt** — web, fetch, code sandbox, calculator, files, shell, stego, conlang, todos…

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness |
| `GET` | `/api/meta` | Provider, tools, bots, skills |
| `POST` | `/api/missions` | `{ "goal", "max_steps", "wait?" }` |
| `GET` | `/api/missions` | List sessions |
| `GET` | `/api/missions/{id}/stream` | SSE live trace |
| `POST` | `/api/chat` | Chief chat (auto-missions) |
| `WS` | `/ws` | Realtime event hub |
| `GET` | `/api/tools` · `/api/skills` | Catalogs |

## CLI

```
/auto <goal>     launch mission with live trace
/missions        list
/tools /skills   catalogs
@researcher …    address a specialist
/bots /spawn /kill
```

## Layout

```
vortex/
├── agent/           # AIAgent, prompt, llm, state, skills, memory, OS
├── tools/           # self-registering tools + registry
├── toolsets.py      # named presets (core/research/coding/…)
├── skills/          # bundled SKILL.md playbooks
├── gateway/         # FastAPI + SSE + WS
├── cli/             # interactive shell
├── frontend/        # Mission Control UI
└── cron/            # extension point
run.py               # python run.py [port] | python run.py cli
```

## Workspace

`~/.vortex/` (override with `VORTEX_HOME`)

```
workspace/   artifacts (reports, plans, code)
sessions/    reserved
skills/      user + learned skills
memory/      MEMORY.md + vectors
vortex.db    sessions · messages · steps · FTS5
```

## License

MIT © 2026 Sanath S Patil

Inspired by [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) — architecture and design patterns, not a fork of the codebase.
