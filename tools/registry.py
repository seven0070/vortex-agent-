"""Central tool registry — Hermes-style self-registering tools.

Each tool module calls ``registry.register()`` at import time.
The agent loop queries schemas and dispatches through this registry.
"""
from __future__ import annotations

import json
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("vortex.tools")

_MAX_ERROR = 2048


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]
    toolsets: List[str] = field(default_factory=lambda: ["core"])
    check_fn: Optional[Callable[[], bool]] = None  # availability gate
    is_dangerous: bool = False


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable[..., Any],
        toolsets: Optional[List[str]] = None,
        check_fn: Optional[Callable[[], bool]] = None,
        is_dangerous: bool = False,
    ) -> None:
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            parameters=parameters or {"type": "object", "properties": {}},
            handler=handler,
            toolsets=toolsets or ["core"],
            check_fn=check_fn,
            is_dangerous=is_dangerous,
        )

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def names(self, toolsets: Optional[List[str]] = None) -> List[str]:
        names = []
        for t in self._tools.values():
            if toolsets and not (set(t.toolsets) & set(toolsets)):
                continue
            if t.check_fn is not None:
                try:
                    if not t.check_fn():
                        continue
                except Exception:
                    continue
            names.append(t.name)
        return sorted(names)

    def list_specs(self, toolsets: Optional[List[str]] = None) -> List[dict]:
        out = []
        for name in self.names(toolsets):
            t = self._tools[name]
            out.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                    "toolsets": t.toolsets,
                    "dangerous": t.is_dangerous,
                }
            )
        return out

    def openai_schemas(self, toolsets: Optional[List[str]] = None) -> List[dict]:
        """OpenAI function-calling schema list."""
        schemas = []
        for name in self.names(toolsets):
            t = self._tools[name]
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
            )
        return schemas

    def description_block(self, toolsets: Optional[List[str]] = None) -> str:
        lines = []
        for s in self.list_specs(toolsets):
            props = list((s["parameters"].get("properties") or {}).keys())
            lines.append(f"- {s['name']}({', '.join(props)}): {s['description']}")
        return "\n".join(lines)

    def dispatch(self, name: str, args: Optional[dict] = None, context: Optional[dict] = None) -> dict:
        """Run a tool and return a normalized result dict."""
        spec = self._tools.get(name)
        if not spec:
            return {"status": "error", "error": f"Unknown tool: {name}", "data": {}}
        if spec.check_fn is not None:
            try:
                if not spec.check_fn():
                    return {"status": "error", "error": f"Tool '{name}' unavailable", "data": {}}
            except Exception as e:
                return {"status": "error", "error": f"Availability check failed: {e}", "data": {}}

        args = dict(args or {})
        ctx = context or {}
        try:
            import inspect

            sig = inspect.signature(spec.handler)
            # inject context if handler accepts it
            if "context" in sig.parameters:
                args["context"] = ctx
            # drop unknown kwargs unless **kwargs
            has_var = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            if not has_var:
                args = {k: v for k, v in args.items() if k in sig.parameters}
            result = spec.handler(**args)
            return self._normalize(result)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            logger.warning("tool %s crashed: %s\n%s", name, err, traceback.format_exc()[-400:])
            return {
                "status": "error",
                "error": err[:_MAX_ERROR],
                "data": {},
            }

    @staticmethod
    def _normalize(result: Any) -> dict:
        if isinstance(result, dict) and "status" in result:
            return result
        if hasattr(result, "to_dict"):
            return result.to_dict()
        if isinstance(result, dict):
            return {"status": "success", "data": result, "message": result.get("message", "")}
        return {"status": "success", "data": {"result": result}, "message": str(result)[:500]}

    def observation(self, result: dict) -> str:
        if result.get("status") != "success":
            err = result.get("error") or result.get("message") or "unknown error"
            return f"ERROR: {str(err)[:_MAX_ERROR]}"
        msg = result.get("message") or "ok"
        data = result.get("data") or {}
        try:
            payload = json.dumps(data, default=str)
        except Exception:
            payload = str(data)
        if len(payload) > 2500:
            payload = payload[:2500] + "…"
        return f"OK — {msg} | data={payload}"


# Singleton
registry = ToolRegistry()
