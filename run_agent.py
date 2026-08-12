#!/usr/bin/env python3
"""Vortex Agent core loop entry (Hermes-style run_agent.py at repo root).

Exposes AIAgent and a thin CLI for one-shot goals:

  python run_agent.py "Calculate 2+2"
  python run_agent.py --council "Research X and write a report"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.run_agent import AIAgent  # noqa: E402
from agent.os import VortexOS  # noqa: E402
from vortex_constants import NAME, VERSION  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=f"{NAME} one-shot runner")
    p.add_argument("goal", nargs="?", help="Goal to run")
    p.add_argument("--council", action="store_true", help="Convene council chamber")
    p.add_argument("--max-steps", type=int, default=12)
    args = p.parse_args(argv)

    if not args.goal:
        print(f"{NAME} v{VERSION}")
        print("Usage: python run_agent.py \"<goal>\" [--council]")
        return 0

    os_ = VortexOS()
    if args.council:
        result = os_.council.convene(
            args.goal, auto_execute=True, background=False, use_chamber=True
        )
        ex = result.get("execution") or {}
        print(ex.get("result") or result.get("consensus") or result)
        return 0 if result.get("status") == "completed" else 1

    agent = os_.agent
    agent.max_steps = args.max_steps
    out = agent.run(args.goal, background=False, max_steps=args.max_steps)
    print(out.get("result") or out.get("error") or out)
    return 0 if out.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
