"""Browser capability — placeholder for future MCP"""
from ..base import ToolResult

class BrowserOpenTool:
    name = "browser.open"
    description = "Open a URL in browser (placeholder, returns intended action)"
    input_schema = {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "browser"
    @staticmethod
    def execute(url: str) -> ToolResult:
        return ToolResult("success", {"url": url, "note": "Browser open simulated"}, "Browser action simulated")

BROWSER_TOOLS = [BrowserOpenTool]
