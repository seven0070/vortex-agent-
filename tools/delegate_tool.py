"""Subagent delegation — Hermes-style isolated child agents."""
from __future__ import annotations

import concurrent.futures
import threading
from typing import Any, Dict, List, Optional

from .registry import registry

# Children must never recurse into more delegation / user-facing side effects
BLOCKED_CHILD_TOOLS = frozenset({"delegate_task"})


def delegate_task(
    goal: str,
    toolset: str = "core",
    max_steps: int = 8,
    context: dict = None,
) -> dict:
    """Spawn an isolated child AIAgent for a focused sub-goal."""
    ctx = context or {}
    parent = ctx.get("agent")
    if parent is None:
        return {"status": "error", "error": "No parent agent in context.", "data": {}}

    from agent.run_agent import AIAgent

    child_toolsets = [toolset] if toolset else ["core"]
    child = AIAgent(
        session_db=parent.session_db,
        vector=parent.vector,
        skills=parent.skills,
        memory_provider=parent.memory_provider,
        toolsets=child_toolsets,
        max_steps=min(int(max_steps or 8), 15),
        event_cb=parent.event_cb,
        parent_id=getattr(parent, "session_id", None),
        role=f"subagent:{toolset}",
        blocked_tools=BLOCKED_CHILD_TOOLS,
    )
    # Don't let children emit as top-level missions unless parent wants
    result = child.run(goal, background=False)
    return {
        "status": "success" if result.get("status") == "completed" else "error",
        "message": f"Subagent finished ({result.get('status')}, {result.get('step_count', 0)} steps).",
        "data": {
            "goal": goal,
            "status": result.get("status"),
            "result": (result.get("result") or "")[:3000],
            "steps": result.get("step_count"),
            "session_id": result.get("id"),
        },
        "error": result.get("error"),
    }


def delegate_batch(
    goals: List[str],
    toolset: str = "core",
    max_steps: int = 6,
    context: dict = None,
) -> dict:
    """Run multiple subagents in parallel."""
    ctx = context or {}
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(goals) or 1)) as pool:
        futs = [
            pool.submit(delegate_task, g, toolset, max_steps, ctx) for g in (goals or [])
        ]
        for f in concurrent.futures.as_completed(futs):
            try:
                results.append(f.result())
            except Exception as e:
                results.append({"status": "error", "error": str(e), "data": {}})
    return {
        "status": "success",
        "message": f"{len(results)} subagents finished.",
        "data": {"results": results},
    }


registry.register(
    "delegate_task",
    "Spawn an isolated subagent with its own context to pursue a sub-goal. "
    "Parent only sees the summary — never the child's intermediate tool calls.",
    {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "Focused sub-goal for the child agent"},
            "toolset": {
                "type": "string",
                "enum": ["core", "research", "coding", "security", "web", "full"],
                "default": "core",
            },
            "max_steps": {"type": "integer", "default": 8},
        },
        "required": ["goal"],
    },
    delegate_task,
    toolsets=["delegate"],
)
