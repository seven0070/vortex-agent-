"""Meta tools: clock, todos, skills browser."""
from __future__ import annotations

from datetime import datetime

from .registry import registry


def now() -> dict:
    dt = datetime.now()
    return {
        "status": "success",
        "message": "Current time.",
        "data": {
            "iso": dt.isoformat(timespec="seconds"),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%S"),
            "weekday": dt.strftime("%A"),
        },
    }


def todo(action: str = "list", item: str = "", context: dict = None) -> dict:
    ctx = context or {}
    board = ctx.setdefault("_todos", [])
    if action == "add" and item:
        board.append({"text": item, "done": False})
        return {"status": "success", "message": "Added.", "data": {"todos": board}}
    if action == "done" and item:
        for t in board:
            if item.lower() in t["text"].lower():
                t["done"] = True
        return {"status": "success", "message": "Updated.", "data": {"todos": board}}
    if action == "clear":
        board.clear()
        return {"status": "success", "message": "Cleared.", "data": {"todos": board}}
    return {"status": "success", "message": f"{len(board)} items.", "data": {"todos": board}}


def skills_list(context: dict = None) -> dict:
    ctx = context or {}
    hub = ctx.get("skills")
    items = hub.list() if hub else []
    return {
        "status": "success",
        "message": f"{len(items)} skills.",
        "data": {"skills": items},
    }


def skill_view(name: str, context: dict = None) -> dict:
    ctx = context or {}
    hub = ctx.get("skills")
    skill = hub.get(name) if hub else None
    if not skill:
        return {"status": "error", "error": f"Skill not found: {name}", "data": {}}
    return {"status": "success", "message": f"Loaded {name}", "data": skill}


registry.register("now", "Return the current local date and time.", {"type": "object", "properties": {}}, now, toolsets=["meta", "core"])
registry.register(
    "todo",
    "Manage a lightweight in-session todo list (list/add/done/clear).",
    {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "add", "done", "clear"], "default": "list"},
            "item": {"type": "string"},
        },
    },
    todo,
    toolsets=["meta", "core"],
)
registry.register(
    "skills_list",
    "List available skills (procedural memory playbooks).",
    {"type": "object", "properties": {}},
    skills_list,
    toolsets=["meta", "core"],
)
registry.register(
    "skill_view",
    "Load a skill's full instructions by name.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
    skill_view,
    toolsets=["meta", "core"],
)
