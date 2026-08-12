"""Memory store / recall tools — wired via runtime context."""
from __future__ import annotations

from .registry import registry


def memory_store(text: str, tag: str = "note", context: dict = None) -> dict:
    ctx = context or {}
    vector = ctx.get("vector")
    if not text:
        return {"status": "error", "error": "text required", "data": {}}
    if vector is not None:
        vector.remember(text, {"tag": tag or "note"})
    # also append to MEMORY.md style file via memory manager if present
    mem = ctx.get("memory_provider")
    if mem is not None and hasattr(mem, "write"):
        try:
            mem.write(text, tag=tag)
        except Exception:
            pass
    return {
        "status": "success",
        "message": "Remembered.",
        "data": {"stored": text[:200], "tag": tag},
    }


def memory_recall(query: str, n: int = 5, context: dict = None) -> dict:
    ctx = context or {}
    vector = ctx.get("vector")
    hits = vector.recall(query, n=int(n or 5)) if vector else []
    return {
        "status": "success",
        "message": f"{len(hits)} memories recalled.",
        "data": {"hits": hits},
    }


registry.register(
    "memory_store",
    "Store a fact/finding in long-term memory.",
    {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "tag": {"type": "string", "default": "note"},
        },
        "required": ["text"],
    },
    memory_store,
    toolsets=["memory", "core"],
)

registry.register(
    "memory_recall",
    "Search long-term memory for related notes.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "n": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    },
    memory_recall,
    toolsets=["memory", "core"],
)
