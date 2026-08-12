"""External tools — list what Vortex actually has loaded, not a fake MCP catalog."""
from ..base import ToolResult


class McpListTool:
    name = "external.mcp.list"
    description = "List registered Vortex tool capabilities"
    input_schema = {"type": "object", "properties": {}}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "external"

    @staticmethod
    def execute() -> ToolResult:
        try:
            from tools import get_registry
            reg = get_registry()
            names = sorted(reg.tools.keys()) if getattr(reg, "tools", None) else []
            cats = reg.categories() if hasattr(reg, "categories") else {}
            return ToolResult("success", {"tools": names, "categories": cats}, f"{len(names)} registered tools")
        except Exception as e:
            return ToolResult("error", {}, f"Registry unavailable: {e}")


EXTERNAL_TOOLS = [McpListTool]
