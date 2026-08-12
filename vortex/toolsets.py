"""Toolset presets — Hermes-style groupings resolved into concrete tool names."""
from __future__ import annotations

from typing import Dict, List, Set

# Named toolsets → tool names (or nested toolset refs prefixed with @)
TOOLSETS: Dict[str, List[str]] = {
    "web": ["web_search", "http_fetch"],
    "files": ["read_file", "write_file", "list_files", "search_files"],
    "code": ["execute_code", "calculator"],
    "shell": ["terminal"],
    "memory": ["memory_store", "memory_recall"],
    "crypto": ["steganography", "glossopetrae"],
    "meta": ["now", "todo", "skills_list", "skill_view"],
    "delegate": ["delegate_task"],
    # Composed presets
    "core": [
        "@web",
        "@files",
        "@code",
        "@shell",
        "@memory",
        "@meta",
    ],
    "research": ["@web", "@files", "@memory", "@meta"],
    "coding": ["@code", "@files", "@shell", "@meta"],
    "security": ["@crypto", "@files", "@shell", "@meta"],
    "full": [
        "@core",
        "@crypto",
        "@delegate",
    ],
    # Swarm role presets
    "role_orchestrator": ["@full"],
    "role_research": ["@research"],
    "role_coding": ["@coding"],
    "role_security": ["@security"],
    "role_scout": ["@web", "@files", "@meta"],
}


def resolve_toolset(name: str, _seen: Set[str] | None = None) -> List[str]:
    """Expand a toolset name (and nested @refs) into a flat unique tool list."""
    _seen = _seen or set()
    if name in _seen:
        return []
    _seen.add(name)
    items = TOOLSETS.get(name, [name] if not name.startswith("@") else TOOLSETS.get(name[1:], []))
    out: List[str] = []
    for item in items:
        if item.startswith("@"):
            out.extend(resolve_toolset(item[1:], _seen))
        else:
            out.append(item)
    # unique, stable
    seen: Set[str] = set()
    unique = []
    for t in out:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def resolve_many(names: List[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for n in names:
        for t in resolve_toolset(n):
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def get_all_toolsets() -> Dict[str, List[str]]:
    return {k: resolve_toolset(k) for k in TOOLSETS}
