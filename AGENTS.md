# Vortex Agent — Development Guide

Instructions for AI coding assistants and developers working on Vortex Agent.

## What Vortex Agent Is

Vortex Agent is an autonomous multi-agent OS with:

- a **narrow core waist** (`agent/`, `run_agent.py`)
- capability at the edges (`tools/`, `skills/`, `plugins/`, council seats)
- a **24-seat Agent Council** + **Council Chamber** (parallel seat workers)
- entrypoints: CLI, Mission Control UI/API gateway

External layout is intentionally aligned with
[Hermes Agent](https://github.com/NousResearch/hermes-agent):

```text
vortex-agent-/
├── run_agent.py          # AIAgent one-shot + export (Hermes run_agent.py)
├── cli.py                # interactive CLI (Hermes cli.py)
├── model_tools.py        # tool discovery/dispatch facade
├── toolsets.py           # named tool groups
├── vortex_constants.py   # VORTEX_HOME, paths, identity
├── utils.py
├── agent/                # core loop, council, chamber, memory, skills hub
├── tools/                # self-registering tools
├── gateway/              # FastAPI + SSE + WS
├── vortex_cli/           # CLI implementation (Hermes hermes_cli/)
├── skills/               # bundled SKILL.md playbooks
├── cron/                 # scheduler extension point
├── plugins/              # memory / platform plugins
├── apps/mission-control/ # Mission Control UI (Hermes apps/)
├── docs/ tests/ scripts/ docker/
├── bin/vortex            # launcher binary
├── vortex/               # installable package facade (python -m vortex)
├── run.py                # repo entrypoint
└── pyproject.toml
```

## Design rules

1. **Core stays narrow.** Prefer skills, toolsets, plugins, and council seats over growing `AIAgent`.
2. **Tools self-register** in `tools/*.py` via `registry.register()`.
3. **Session surface ≠ process env.** Gate session capabilities from session context, not ambient env vars.
4. **Council chamber workers never re-enter council** (`convene_council` blocked).
5. **`.env` is secrets only.** Behavioral knobs belong in config YAML.

## Commands

```bash
python run.py doctor
python run.py                 # UI+API :8765
python run.py cli
python run_agent.py "goal"
python cli.py
./bin/vortex version
```
