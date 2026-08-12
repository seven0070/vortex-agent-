# Vortex Agent Architecture

## Overview

Vortex Agent is an autonomous multi-agent operating system with three execution modes:

1. **Solo mission** — one `AIAgent` runs plan → act → observe until done  
2. **Council** — 24 project-inspired seats brief, propose, critique, and vote  
3. **Chamber** — after an approve/amend vote, selected seats run as parallel worker agents; the chief merges artifacts into `FINAL.md`

## Layout (Hermes-aligned)

```text
agent/           AIAgent, council, chamber, memory, skills hub, OS
tools/           self-registering tools (registry.register)
toolsets.py      named tool groups
gateway/         FastAPI + SSE + WebSocket + static Mission Control
vortex_cli/      interactive CLI
skills/          bundled SKILL.md playbooks
apps/mission-control/   web app UI
vortex/          install facade + bundled data/
run_agent.py     one-shot runner
cli.py / run.py / bin/vortex
```

## Key flows

### Solo

```text
POST /api/missions {goal}
  → AIAgent.run
  → offline planner or LLM emits JSON actions
  → tools.registry.dispatch
  → finish
```

### Council + chamber

```text
POST /api/council {goal, use_chamber:true}
  → brief (all seats, parallel)
  → propose (builder seats)
  → critique (gate seats)
  → vote (weighted; Prime/Hermes hard-veto on harm)
  → CouncilChamber.dispatch seat workers (scoped toolsets)
  → chief merge → workspace/council/<id>/FINAL.md
```

## Safety

- Shell tool is allowlisted  
- Files sandboxed to `~/.vortex/workspace`  
- Chamber workers cannot call `convene_council`  
- Harmful goals are rejected by council hard-veto  

## Data

| Path | Purpose |
|------|---------|
| `~/.vortex/vortex.db` | sessions, steps, events, FTS5 |
| `~/.vortex/workspace/` | artifacts |
| `~/.vortex/memory/` | MEMORY.md + vectors |
| `~/.vortex/skills/` | learned skills |

## Extending

- **New tool**: add `tools/my_tool.py` that calls `registry.register(...)` and import it from `tools/__init__.py`  
- **New toolset**: edit `toolsets.py`  
- **New council seat**: add a `Seat(...)` in `agent/council.py` and persona branches in `PersonaMind`  
- **Plugin surface**: `plugins/` is reserved for future memory/platform adapters  
