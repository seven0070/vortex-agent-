"""
Tool Registry — centralized tool discovery + Governance check + capability layer
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from .base import ToolCapability, ToolResult
from .legacy import TOOL_CLASSES as LEGACY_TOOLS

class ToolRegistry:
    def __init__(self, governance=None):
        self.governance = governance
        self.tools: Dict[str, Any] = {}
        self._load_legacy()
        self._load_extended()

    def _load_legacy(self):
        for t in LEGACY_TOOLS:
            self.tools[t.name] = t

    def _load_extended(self):
        # import extended tools lazily
        try:
            from .filesystem import FILESYSTEM_TOOLS
            for t in FILESYSTEM_TOOLS:
                self.tools[t.name] = t
        except Exception as e:
            pass
        try:
            from .shell import SHELL_TOOLS
            for t in SHELL_TOOLS:
                self.tools[t.name] = t
        except:
            pass
        try:
            from .web import WEB_TOOLS
            for t in WEB_TOOLS:
                self.tools[t.name] = t
        except:
            pass
        try:
            from .code import CODE_TOOLS
            for t in CODE_TOOLS:
                self.tools[t.name] = t
        except:
            pass
        try:
            from .browser import BROWSER_TOOLS
            for t in BROWSER_TOOLS:
                self.tools[t.name] = t
        except:
            pass
        try:
            from .github import GITHUB_TOOLS
            for t in GITHUB_TOOLS:
                self.tools[t.name] = t
        except:
            pass
        try:
            from .database import DATABASE_TOOLS
            for t in DATABASE_TOOLS:
                self.tools[t.name] = t
        except:
            pass
        try:
            from .communication import COMM_TOOLS
            for t in COMM_TOOLS:
                self.tools[t.name] = t
        except:
            pass
        try:
            from .external import EXTERNAL_TOOLS
            for t in EXTERNAL_TOOLS:
                self.tools[t.name] = t
        except:
            pass

    def get(self, name: str):
        return self.tools.get(name)

    def list(self) -> List[Dict[str, Any]]:
        out = []
        for name, t in self.tools.items():
            if hasattr(t, 'to_dict'):
                out.append(t.to_dict())
            elif hasattr(t, 'description'):
                out.append({
                    "name": getattr(t, 'name', name),
                    "description": getattr(t, 'description', ''),
                    "permissions": getattr(t, 'permissions', []),
                    "risk_level": getattr(t, 'risk_level', 'low'),
                    "category": getattr(t, 'category', 'general'),
                })
            else:
                out.append({"name": name})
        return out

    def execute(self, name: str, governance_check: bool = True, agent: str = "chief", **kwargs) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult("error", {}, f"Tool {name} not found")

        # Governance check before execution
        if governance_check and self.governance:
            decision = self.governance.evaluate(task=f"tool:{name}", context={"tool": name, "args": kwargs, "agent": agent}, agent=agent, action="execute")
            if decision["action"] == "DENY":
                return ToolResult("error", {}, f"Governance DENY: {decision['reason']}")
            if decision["action"] == "ESCALATE":
                # escalate is not allow — refuse unattended execution
                return ToolResult("error", {}, f"Governance ESCALATE: {decision['reason']}")

        try:
            result = tool.execute(**kwargs)
            if isinstance(result, dict):
                # normalize
                return ToolResult(result.get("status", "success"), result.get("data", {}), result.get("message", ""))
            return result
        except Exception as e:
            return ToolResult("error", {}, f"Tool {name} crashed: {e}")

    def categories(self) -> Dict[str, List[str]]:
        cats: Dict[str, List[str]] = {}
        for name, t in self.tools.items():
            cat = getattr(t, 'category', 'general')
            cats.setdefault(cat, []).append(name)
        return cats
