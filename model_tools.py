"""Tool discovery + dispatch facade (Hermes model_tools.py counterpart)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import tools  # noqa: F401 — register tools
from tools.registry import registry
from toolsets import resolve_many, get_all_toolsets


def list_tools(toolsets: Optional[List[str]] = None) -> List[dict]:
    if toolsets:
        names = set(resolve_many(toolsets))
        return [s for s in registry.list_specs() if s["name"] in names]
    return registry.list_specs()


def openai_schemas(toolsets: Optional[List[str]] = None) -> List[dict]:
    if toolsets:
        names = set(resolve_many(toolsets))
        return [
            s
            for s in registry.openai_schemas()
            if s.get("function", {}).get("name") in names
        ]
    return registry.openai_schemas()


def handle_function_call(
    name: str, args: Optional[dict] = None, context: Optional[dict] = None
) -> dict:
    return registry.dispatch(name, args or {}, context=context or {})


def toolsets_catalog() -> Dict[str, List[str]]:
    return get_all_toolsets()


__all__ = [
    "list_tools",
    "openai_schemas",
    "handle_function_call",
    "toolsets_catalog",
    "registry",
]
