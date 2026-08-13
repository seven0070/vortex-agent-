"""Attach the code-evolution engine to an agent (kept separate to avoid import cycles)."""
from __future__ import annotations


def init_code_evolution(agent) -> None:
    from code_mutation import CodeEvolution
    agent.code_evolution = CodeEvolution(
        agent=agent,
        memory=getattr(agent, "memory", None),
        governance=getattr(agent, "governance", None),
    )
