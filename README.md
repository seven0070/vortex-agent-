# Vortex Agent — Full Architecture 0.4.0

A local swarm agent with **rapid self-improvement + Ultron-style evolution** — it rescues a miss in the same turn, stores the lesson in a **knowledge graph + vector memory**, and only keeps mutations that raise a frozen eval score.

```
observe → rescue → reflect → mutate → eval → promote (or revert)
          ↕
     Evolution Engine: Observe → Weakness → Hypothesis → Candidate → Sandbox → Tests → Benchmarks → Security → Compare → Canary → Deploy → Monitor → Rollback
```

No live LLM required. Tools run sandboxed; RSI + Evolution sit on top as the learning loop.

## Reference Inspirations (architecture borrowed, not wholesale merged)

| Vortex capability | Reference repo | What we took |
|---|---|---|
| Memory + knowledge graph | Cognee | Graph + vector memory, persistent context, cross-agent knowledge, `remember/recall/forget/improve` |
| Memory algorithm | Mem0 | Entity linking, temporal memory, hybrid retrieval, user/session/agent memory |
| Orchestration | LangGraph | Stateful graphs, durable execution, branching, retries, human checkpoints |
| Multi-agent workflows | Microsoft Agent Framework | Sequential/concurrent/handoff/group collaboration patterns |
| Autonomous coding / self-improvement | OpenHands | Agents that inspect files, modify code and execute development tasks (versioned releases) |
| Policy / governance | Open Policy Agent | Explicit policy decisions outside LLM → ALLOW/DENY/ESCALATE |
| Observability | OpenTelemetry Python | Traces, metrics, execution telemetry |
| Tools / external capabilities | MCP Servers | Standardized tool/data interfaces, capability declaration |
| Output/input safety | Guardrails AI | Validation and guardrails around model outputs |

## New Architecture

```
                    ┌──────────────────────┐
                    │      INTERFACE       │  Web / Desktop / CLI
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │      SOVEREIGN       │  identity/objectives/state/priorities/lifecycle
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │      GOVERNANCE      │  policy/risk/permissions/approvals/audit (OPA-style)
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │      RESOLUTION      │  correctness/reliability/evidence/cost/latency/risk/policy
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │       COUNCIL        │  Researcher/Planner/Engineer/Critic/Security/Strategist/Verifier
                    └──────────┬───────────┘  proposal→analyses→critic→evidence→confidence→vote→resolution
                               │
                    ┌──────────▼───────────┐
                    │    ORCHESTRATION     │  Goal→Understand→Plan→Decompose→Route→Execute→Observe→Evaluate→Recover→Resolve
                    └───────┬───────┬──────┘  stateful graph, durable, LangGraph-inspired
                            │       │
                 ┌──────────▼─┐ ┌─▼──────────┐
                 │   MEMORY   │ │   TOOLS    │  filesystem/browser/shell/github/database/web/code/communication/external
                 │ graph/RAG  │ │ MCP/etc.   │  7 layers: working/episodic/semantic/procedural/user/agent + KG
                 └────────────┘ └────────────┘

                         ↕
                SELF-IMPROVEMENT      Observe → Find weakness → Hypothesis → Candidate → Sandbox → Regression → Benchmarks → Security → Compare → Canary → Deploy → Monitor → Rollback
                         ↕
              EVALUATION + TELEMETRY  Vortex Benchmark: reasoning/planning/tool_selection/coding/memory/multi_agent/reliability/safety/cost/latency/regression
                         ↕
                  NEW GENERATION      vortex/releases/v001/ evolution_record.json
```

### 1. Memory Graph (Cognee/Mem0 concepts)

```
Vortex Memory
├── Working Memory  (immediate 50-turn window)
├── Episodic Memory (events, traces, timelines)
├── Semantic Memory (facts + vector+graph)
├── Procedural Memory (skills, bug patterns)
├── User Memory (preferences, recurring intents)
├── Agent Memory (per-agent + cross-agent knowledge)
└── Knowledge Graph (entity linking, temporal, remember/recall/forget/improve)
Flow: interaction → extract facts/events/lessons → classify → store vector+graph → link entities → retrieve → inject into Orchestrator
```

`backend/knowledge_graph.py` implements Cognee's `remember/recall/forget/improve` with SQLite nodes/edges + hybrid vector/graph retrieval.
`backend/memory_types.py` implements 6 memory layers.
`backend/memory.py` now exposes `remember(text, kind, meta)`, `recall(query, n, hybrid)`, `full_context_for_orchestrator(goal)`.

### 2. Stateful Orchestration (LangGraph)

`backend/orchestration/`:
- `state.py` — `VortexState` + `TaskNode` + durable `StateManager`
- `planner.py` — Understand → Plan → Decompose, intent classification, memory injection
- `router.py` — tool/agent affinity, handoff pattern, council decision
- `executor.py` — runs tasks with governance check, retry mutation
- `recovery.py` — Observe → Evaluate → Recover, mutate args
- `graph.py` — state machine graph with branching, retries, human checkpoints, council node, resolution node

### 3. Council (Microsoft Agent Framework patterns + own protocol)

`backend/council.py` — `VortexCouncil`:
- Roles: Researcher, Planner, Engineer, Critic, Security, Strategist, Verifier (with weights)
- Protocol: proposal → independent analyses (concurrent) → critic phase → evidence comparison → confidence scoring → weighted vote → resolution synthesis
- Cross-agent knowledge sharing via `agent_memory`

### 4. Resolution

`backend/resolution.py` — `VortexResolver`:
- Scores candidates on correctness, reliability, evidence, cost, latency, risk, policy compliance, historical success
- Can request replan: “None good enough; return to planning”

### 5. Governance (OPA-style)

`backend/governance/`:
- `policy.py` — declarative policies, priority-ordered, DENY overrides
- `permissions.py` — agent → allowed actions, protected files
- `approvals.py` — what requires human approval
- `risk.py` — risk scoring heuristic
- `audit.py` — audit trail to file + memory
- Unified `Governance.evaluate(task, context, agent, action)` → ALLOW/DENY/ESCALATE

Example:
```
Agent requests: "Modify orchestrator.py"
Governance: Is agent allowed? Is file protected? Does change require approval? Tests pass? Security scan? Risk acceptable? → ALLOW/DENY/ESCALATE
```

### 6. Sovereign

`backend/sovereign/`:
- `identity.py` — WHO AM I?
- `objectives.py` — WHAT AM I TRYING TO ACHIEVE?
- `state.py` — WHAT STATE AM I IN? WHAT AM I ALLOWED TO CHANGE?
- `priorities.py` — WHAT ARE MY CURRENT PRIORITIES?
- `lifecycle.py` — born → operational → canary → deploy → monitor → rollback
- Sovereign **does not directly execute tools**, only sets objectives/constraints.

### 7. Tool Ecosystem (MCP-inspired)

`backend/tools/` standardized capabilities:
Each tool declares `name, description, input_schema, output_schema, permissions, risk_level, timeout, rollback_method`

```
tools/
├── filesystem/ (read/write/list)
├── browser/ (open)
├── shell/ (exec sandboxed)
├── github/ (status)
├── database/ (query memory.db SELECT)
├── web/ (search mock + fetch)
├── code/ (analyze/test + codeforge)
├── communication/ (translate/hide)
└── external/ (mcp.list)
```

`ToolRegistry` + governance check before execution.
Backward compat: `from tools import TOOL_CLASSES` still works (loads package).

### 8. Self-Improvement Evolution Engine (OpenHands-style)

`backend/self_improve.py` now two layers:
- **RapidSelfImprovement** (existing): observe→rescue→reflect→mutate→eval→promote per turn
- **EvolutionEngine** (new):
```
Observe → Find weakness → Hypothesis → Candidate → Modify → Sandbox → Regression Tests → Benchmarks → Security Analysis → Compare Baseline ↙↘ (worse->reject, better->stage->canary->deploy->monitor->rollback)
```
- Versioned candidates in `~/.vortex/releases/v001/` with `candidate.json`, `evolution_record.json` containing generation_id, parent_generation, change_set, benchmark_results, security_results, performance_results, decision.

### 9. Evaluation — Vortex Benchmark

`backend/evals.py`:
- Preserves original 7 cases for fast eval
- Adds 15 extended cases for comprehensive benchmark categories
- `Vortex Benchmark`: reasoning, planning, tool selection, coding, memory recall, multi-agent, reliability, safety, cost, latency, regression
- `VortexBenchmark.compare(baseline, candidate)` → diff by category + decision promote/reject (improvement earned, not assumed)

### 10. Observability (OpenTelemetry)

`backend/observability/`:
- `tracer.py` — trace_id, span_id, parent_id, attributes, events, duration, final_outcome
- `metrics.py` — counters, histograms, gauges
- Every execution: trace_id, task_id, agent_id, generation_id, model, tokens, latency, tool_calls, memory_hits, errors, score, final_outcome

### 11. Security layer

Before autonomous code modification:
```
Code Agent → isolated sandbox → filesystem restrictions → network restrictions → resource limits → tests → security scan → governance
```

## Swarm — upgraded

| Bot | Role | Council mapping |
|---|---|---|
| `chief` | Orchestrates, compiles intents, delegates | Planner/Strategist |
| `researcher` | Research notes + memory recall | Researcher/Critic |
| `architect` | Sandboxed Python (`codeforge`) | Engineer/Verifier |
| `cipher` | Conlang + steganography + security | Security |
| `improver` | Closes RSI loop + evolution | Evolution |
| `planner` | Planning specialist | Planner |
| `critic` | Critic specialist | Critic |
| `strategist` | Strategic alignment | Strategist |
| `verifier` | Verification specialist | Verifier |

Chief can now run full orchestration via `orchestrate: <goal>` or via API `/api/chat/orchestrated`.

## Rapid self-improvement (still)

1. Observe — every turn scored + SQLite traces + episodic memory + knowledge graph nodes
2. Rescue — natural-language math, Fibonacci, hide/reveal, translate compiled to tool calls
3. Reflect — successes become routing lessons + token weights
4. Retry — failed calls mutated once
5. Eval — frozen judges (original suite) + Vortex Benchmark comprehensive
6. Promote — generation kept only if suite does not regress; evolution engine stages canary → deploy → monitor → rollback with governance

## Run

```bash
cd vortex-agent/backend
python -m pip install -r requirements.txt
python main.py 8765          # API + full dashboard on http://0.0.0.0:8765
python cli.py                # terminal swarm (new commands: /council /governance /sovereign /tools /memory /graph /orchestrate /benchmark /observability)
python -m unittest discover tests -v
```

Override data dir with `VORTEX_HOME=/tmp/vortex-dev`.

## Desktop app (PyQt6, Windows native)

The repository now includes a desktop client at `vortex-agent/desktop/` that connects to the same FastAPI backend (`vortex-agent/backend/main.py`) used by the web dashboard.

### Features

- Real-time chat + memory recall
- Dashboard with health/stats/observability telemetry
- Knowledge graph viewer
- Council deliberation viewer
- Governance + policy evaluation panel
- Tool execution monitor
- Orchestration run/history visualizer
- Audit trail + logs viewer (filterable)
- Benchmark runner
- Settings panel with connection status indicator
- System tray integration
- Local backend auto-start (or connect to remote backend)

### Run desktop client

```bash
cd vortex-agent/desktop
python -m pip install -r requirements.txt
python main.py
```

By default the desktop app tries `http://127.0.0.1:8765` and auto-starts the local backend when enabled in settings.

### Build Windows executable

From Windows 10/11:

```bat
cd vortex-agent\desktop
build_windows.bat
```

### CLI new commands

```
/council               council status
/deliberate <goal>     run council deliberation
/governance            governance policies + audit
/sovereign             sovereign identity/objectives/state
/tools                 list tool capabilities by category
/memory <query>        hybrid memory recall (vector+graph+episodic+agent)
/graph                 knowledge graph stats + top nodes
/orchestrate <goal>    run full orchestration graph
/benchmark             Vortex comprehensive benchmark
/observability         traces + metrics
```

### HTTP new endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat` | chat, optional `{"orchestrated": true}` |
| POST | `/api/chat/orchestrated` | full graph path |
| GET | `/api/memory?query=` | hybrid recall |
| POST | `/api/memory/remember` | remember fact/event |
| GET | `/api/memory/graph` | KG nodes |
| GET | `/api/council` | council status |
| POST | `/api/council/deliberate` | council protocol |
| GET | `/api/governance` | policies + audit |
| POST | `/api/governance/evaluate` | OPA-style evaluation |
| GET | `/api/sovereign` | identity/objectives/state |
| GET | `/api/tools` | capability list + categories |
| POST | `/api/tools/exec` | execute tool with governance |
| GET | `/api/orchestration` | recent states |
| POST | `/api/orchestration/run` | run graph |
| GET | `/api/observability` | traces + metrics |
| POST | `/api/resolution/resolve` | resolve candidates |
| POST | `/api/rsi/eval/benchmark` | comprehensive benchmark |

## Layout final

```
vortex-agent/backend/
  memory.py, memory_types.py, knowledge_graph.py, vector_memory.py
  orchestration/ state.py planner.py router.py executor.py recovery.py graph.py
  council.py
  resolution.py
  governance/ policy.py permissions.py approvals.py risk.py audit.py
  sovereign/ identity.py objectives.py state.py priorities.py lifecycle.py
  tools/ base.py legacy.py registry.py filesystem/ browser/ shell/ github/ database/ web/ code/ communication/ external/
  observability/ tracer.py metrics.py
  self_improve.py (RSI + EvolutionEngine)
  evals.py (Vortex Benchmark)
  swarm.py (VortexAgent + Council integration)
  main.py (FastAPI 0.4.0)
  cli.py
  static/index.html (full architecture dashboard)
  tests/test_rsi.py + test_architecture.py
vortex-agent/desktop/
  main.py (PyQt6 desktop entry)
  api_client.py + backend_manager.py + config.py
  ui/main_window.py
  requirements.txt + build_windows.bat
```

## Implementation order completed

1. Memory graph → Cognee/Mem0 concepts ✅
2. Stateful orchestration → LangGraph concepts ✅
3. Council → MS Agent Framework patterns ✅
4. Resolution → built ✅
5. Governance → OPA-style ✅
6. Sovereign → built ✅
7. Tool ecosystem → MCP ✅
8. Self-improvement → OpenHands-style coding agent + evolution ✅
9. Evaluation → Vortex Benchmark ✅
10. Observability → OpenTelemetry-inspired ✅
11. Security/sandboxing ✅
12. Interface expansion ✅

Vortex risks becoming a dependency pile — we selectively imported mechanisms, kept local fallbacks, and preserved backward compatibility (`from tools import TOOL_CLASSES` still works).
