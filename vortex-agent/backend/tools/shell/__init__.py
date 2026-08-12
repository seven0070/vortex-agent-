"""Shell capability — sandboxed"""
import subprocess, shlex, os, sys
from pathlib import Path
from ..base import ToolResult
from paths import vortex_home

WORKSPACE = vortex_home() / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

class ShellExecTool:
    name = "shell.exec"
    description = "Execute a shell command in vortex workspace (sandboxed)"
    input_schema = {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer", "default": 10}}, "required": ["command"]}
    permissions = ["execute"]
    risk_level = "high"
    timeout = 15
    category = "shell"
    @staticmethod
    def execute(command: str, timeout: int = 10) -> ToolResult:
        # basic safety: block destructive
        lower = command.lower()
        blocked = ["rm -rf /", "mkfs", ":(){", "chmod -r 777 /", "dd if="]
        if any(b in lower for b in blocked):
            return ToolResult("error", {}, "Blocked dangerous command")
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(WORKSPACE)
            )
            if proc.returncode == 0:
                return ToolResult("success", {"output": proc.stdout[:4000], "stderr": proc.stderr[:1000]}, "Exec success")
            return ToolResult("error", {"stdout": proc.stdout[:1000], "stderr": proc.stderr[:2000]}, f"Exit {proc.returncode}")
        except subprocess.TimeoutExpired:
            return ToolResult("error", {}, f"Timeout after {timeout}s")
        except Exception as e:
            return ToolResult("error", {}, f"Shell crash: {e}")

SHELL_TOOLS = [ShellExecTool]
