"""
Base Capability — standardized tool declaration (MCP-inspired)

Each tool declares:
name, description, input_schema, output_schema, permissions, risk_level, timeout, rollback_method
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable
import time

@dataclass
class ToolCapability:
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    permissions: list = field(default_factory=lambda: ["read"])
    risk_level: str = "low"  # low, medium, high, critical
    timeout: int = 30
    rollback_method: Optional[str] = None
    category: str = "general"
    version: str = "1.0.0"
    execute_fn: Optional[Callable] = None

    def execute(self, **kwargs) -> Any:
        if self.execute_fn:
            return self.execute_fn(**kwargs)
        raise NotImplementedError(f"Tool {self.name} has no execute_fn")

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "permissions": self.permissions,
            "risk_level": self.risk_level,
            "timeout": self.timeout,
            "rollback_method": self.rollback_method,
            "category": self.category,
            "version": self.version,
        }

@dataclass
class ToolResult:
    status: str
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self):
        return {"status": self.status, "data": self.data, "message": self.message}
