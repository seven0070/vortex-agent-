# Vortex Agent

A local swarm agent with **rapid self-improvement** — it rescues a miss in the same turn, stores the lesson, and only keeps mutations that raise a frozen eval score.

```
observe → rescue → reflect → mutate → eval → promote (or revert)
```

No live LLM is required. Phase-1 tools still run sandboxed; RSI sits on top as the learning loop.

## Swarm

| Bot | Role |
|---|---|
| `chief` | Orchestrates, compiles intents, delegates |
| `researcher` | Research notes + memory recall |
| `architect` | Sandboxed Python (`codeforge`) |
| `cipher` | Conlang + steganography |
| `improver` | Closes the RSI loop |

## Rapid self-improvement

1. **Observe** — every turn is scored and written to SQLite (`traces`).
2. **Rescue** — a weak “I don’t have an LLM” reply is intercepted mid-turn. Natural-language math, Fibonacci, hide/reveal, and translate are compiled into tool calls and executed immediately.
3. **Reflect** — successes become routing lessons and token weights on a learned router.
4. **Retry** — failed `codeforge` / stego calls are mutated once (e.g. wrap an expression in `print`).
5. **Eval** — a canned suite with deterministic judges. Learning is frozen while it runs.
6. **Promote** — a generation is kept only if the suite does not regress.

Talk to it like a human. After `what is 12 times 8` it answers `96` and remembers `times → codeforge` for the next miss.

## Run

```bash
cd vortex-agent/backend
python -m pip install -r requirements.txt
python main.py 8765          # API + dashboard on http://0.0.0.0:8765
python cli.py                # terminal swarm
python -m unittest tests/test_rsi.py
```

Override the data dir with `VORTEX_HOME=/tmp/vortex-dev`.

### CLI

```
/improve     RSI status + top lessons
/evolve      run a full eval → mutate → promote cycle
/eval        frozen suite only
/lessons     active lessons
@improver run cycle
```

### HTTP

| Method | Path | |
|---|---|---|
| GET | `/` | RSI dashboard |
| POST | `/api/chat` | `{ "message": "..." }` |
| GET | `/api/rsi` | generation, lessons, traces |
| POST | `/api/rsi/cycle` | improve cycle |
| POST | `/api/rsi/eval` | suite |

## Layout

```
vortex-agent/backend/
  swarm.py          bots + chief
  self_improve.py   RSI engine (router, compiler, reflector)
  evals.py          frozen judges
  memory.py         SQLite including traces / lessons / generations
  tools.py          glossopetrae, steganography, codeforge
  main.py           FastAPI
  cli.py            terminal
  static/index.html dashboard
```
