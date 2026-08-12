"""Filesystem capability"""
import os
from pathlib import Path
from ..base import ToolResult, ToolCapability
from paths import vortex_home

WORKSPACE = vortex_home() / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

class ReadFileTool:
    name = "filesystem.read"
    description = "Read a file from vortex workspace"
    input_schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "filesystem"
    @staticmethod
    def execute(path: str) -> ToolResult:
        p = Path(path)
        if not p.is_absolute():
            p = WORKSPACE / path
        # sandbox: must be within workspace
        try:
            p = p.resolve()
            if WORKSPACE.resolve() not in p.parents and p != WORKSPACE.resolve():
                return ToolResult("error", {}, "Path outside workspace")
            if not p.exists():
                return ToolResult("error", {}, f"File not found: {path}")
            content = p.read_text()[:8000]
            return ToolResult("success", {"content": content, "path": str(p)}, "File read")
        except Exception as e:
            return ToolResult("error", {}, f"Read failed: {e}")

class WriteFileTool:
    name = "filesystem.write"
    description = "Write a file to vortex workspace"
    input_schema = {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path","content"]}
    permissions = ["write"]
    risk_level = "medium"
    timeout = 5
    category = "filesystem"
    rollback_method = "delete_file"
    @staticmethod
    def execute(path: str, content: str) -> ToolResult:
        try:
            p = Path(path)
            if not p.is_absolute():
                p = WORKSPACE / path
            p = p.resolve()
            if WORKSPACE.resolve() not in p.parents and p != WORKSPACE.resolve():
                return ToolResult("error", {}, "Path outside workspace")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return ToolResult("success", {"path": str(p), "bytes": len(content)}, "File written")
        except Exception as e:
            return ToolResult("error", {}, f"Write failed: {e}")

class ListFilesTool:
    name = "filesystem.list"
    description = "List files in workspace"
    input_schema = {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "filesystem"
    @staticmethod
    def execute(path: str = ".") -> ToolResult:
        try:
            p = Path(path)
            if not p.is_absolute():
                p = WORKSPACE / path
            p = p.resolve()
            if WORKSPACE.resolve() not in p.parents and p != WORKSPACE.resolve():
                return ToolResult("error", {}, "Path outside workspace")
            files = [str(f.relative_to(WORKSPACE)) for f in p.iterdir()] if p.is_dir() else [str(p)]
            return ToolResult("success", {"files": files[:100]}, f"Listed {len(files)} files")
        except Exception as e:
            return ToolResult("error", {}, f"List failed: {e}")

FILESYSTEM_TOOLS = [ReadFileTool, WriteFileTool, ListFilesTool]
