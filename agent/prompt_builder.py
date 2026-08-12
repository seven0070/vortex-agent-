"""System prompt assembly — stable → context → volatile tiers (Hermes-style)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from vortex_constants import NAME, VERSION, WORKSPACE


IDENTITY = f"""You are {NAME} v{VERSION}, an autonomous multi-agent operating system.
You plan carefully, use tools, observe results, and iterate until the goal is complete.
You may convene the Agent Council and dispatch chamber workers for complex goals.
Be concise. Prefer concrete actions over chatter.
You create skills from successful runs and recall past knowledge when useful.
Never invent tool results — always call tools to get real data.
"""

TOOL_PROTOCOL = """## Tool protocol
When you need a tool, reply ONLY with a JSON object:
{"thought":"brief reasoning","action":"tool_name","args":{...}}

When the goal is complete (or you must answer the user), reply ONLY with:
{"thought":"brief reasoning","action":"finish","args":{"result":"your final answer"}}

Do not wrap JSON in markdown fences. Do not add prose outside the JSON.
"""


def build_system_prompt(
    tools_block: str = "",
    skills_block: str = "",
    memory_block: str = "",
    role: str = "agent",
    extra: str = "",
) -> str:
    """Assemble ordered prompt tiers."""
    # stable
    parts = [IDENTITY, TOOL_PROTOCOL]
    if tools_block:
        parts.append("## Available tools\n" + tools_block)
    if skills_block:
        parts.append(skills_block)

    # context
    parts.append(f"## Runtime\n- role: {role}\n- workspace: {WORKSPACE}\n")
    if extra:
        parts.append(extra)

    # volatile
    parts.append(f"## Clock\n{datetime.now().isoformat(timespec='seconds')}")
    if memory_block:
        parts.append(memory_block)

    return "\n\n".join(p.strip() for p in parts if p and p.strip())
