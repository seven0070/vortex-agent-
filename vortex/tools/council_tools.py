"""Council tools — convene deliberation from inside the autonomous loop."""
from __future__ import annotations

from .registry import registry


def convene_council(
    goal: str,
    seats: str = "",
    auto_execute: bool = True,
    context: dict = None,
) -> dict:
    """Convene the Agent Council on a goal. Blocks until deliberation (+ optional exec) finishes."""
    ctx = context or {}
    council = ctx.get("council")
    if council is None:
        # try parent agent / os
        agent = ctx.get("agent")
        council = getattr(agent, "council", None) if agent else None
    if council is None:
        return {
            "status": "error",
            "error": "Council not available in this runtime context.",
            "data": {},
        }

    seat_ids = None
    if seats:
        seat_ids = [s.strip() for s in seats.replace(";", ",").split(",") if s.strip()]

    result = council.convene(
        goal=goal,
        seat_ids=seat_ids,
        auto_execute=bool(auto_execute),
        background=False,
    )
    return {
        "status": "success" if result.get("status") in ("completed", "voted") else result.get("status", "error"),
        "message": f"Council {result.get('status')} · decision="
        f"{(result.get('directive') or {}).get('decision', '?')}",
        "data": {
            "council_id": result.get("id"),
            "decision": (result.get("directive") or {}).get("decision"),
            "tally": result.get("tally"),
            "consensus": result.get("consensus"),
            "actions": (result.get("directive") or {}).get("actions"),
            "execution_status": (result.get("execution") or {}).get("status"),
            "result": _short_result(result),
        },
    }


def council_status(council_id: str = "", context: dict = None) -> dict:
    ctx = context or {}
    council = ctx.get("council")
    agent = ctx.get("agent")
    if council is None and agent is not None:
        council = getattr(agent, "council", None)
    if council is None:
        return {"status": "error", "error": "Council not available.", "data": {}}
    if council_id:
        s = council.get(council_id)
        if not s:
            return {"status": "error", "error": "Not found", "data": {}}
        return {"status": "success", "message": s.get("status"), "data": s}
    return {
        "status": "success",
        "message": f"{len(council.list_sessions())} sessions",
        "data": {"sessions": council.list_sessions()[:20], "seats": council.list_seats()},
    }


def _short_result(result: dict) -> str:
    ex = result.get("execution") or {}
    body = ex.get("result") or result.get("consensus") or ""
    return str(body)[:2000]


registry.register(
    name="convene_council",
    description=(
        "Convene the AI Agent Council to deliberate on a complex or high-stakes goal. "
        "Specialists brief, propose, critique, and vote; the autonomous chief then executes "
        "the consensus directive. Use for multi-faceted goals, disputes, or when you want "
        "adversarial review before acting."
    ),
    parameters={
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "The question or mission for the council"},
            "seats": {
                "type": "string",
                "description": "Optional comma-separated seat ids "
                "(strategist,researcher,architect,critic,ethicist,cipher,executor)",
            },
            "auto_execute": {
                "type": "boolean",
                "default": True,
                "description": "If true, chief executes the approved directive after the vote",
            },
        },
        "required": ["goal"],
    },
    handler=convene_council,
    toolsets=["council", "delegate", "full"],
)

registry.register(
    name="council_status",
    description="List council seats/sessions or fetch one council session by id.",
    parameters={
        "type": "object",
        "properties": {"council_id": {"type": "string"}},
    },
    handler=council_status,
    toolsets=["council", "meta", "full"],
)
