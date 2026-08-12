"""GitHub capability"""
from ..base import ToolResult
import subprocess

class GithubStatusTool:
    name = "github.status"
    description = "Check git status of vortex repo"
    input_schema = {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}
    permissions = ["read", "execute"]
    risk_level = "low"
    timeout = 10
    category = "github"
    @staticmethod
    def execute(path: str = ".") -> ToolResult:
        try:
            proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5, cwd=path)
            return ToolResult("success", {"status": proc.stdout[:2000]}, "Git status")
        except Exception as e:
            return ToolResult("error", {}, f"Git status failed: {e}")

GITHUB_TOOLS = [GithubStatusTool]
