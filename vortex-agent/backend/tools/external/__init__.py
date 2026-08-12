"""External tools — MCP-style standardized external capabilities placeholder"""
from ..base import ToolResult

class McpListTool:
    name = "external.mcp.list"
    description = "List available MCP servers (mock)"
    input_schema = {"type": "object", "properties": {}}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "external"
    @staticmethod
    def execute() -> ToolResult:
        # In real MCP, would list servers from https://github.com/modelcontextprotocol/servers
        return ToolResult("success", {"servers": ["filesystem", "github", "browser", "database", "fetch"]}, "MCP servers (mock)")

EXTERNAL_TOOLS = [McpListTool]
