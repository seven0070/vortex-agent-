"""Browser capability — honest: no attached display/session means no fake success."""
from ..base import ToolResult


class BrowserOpenTool:
    name = "browser.open"
    description = "Open a URL in a real browser session if one is attached"
    input_schema = {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "browser"

    @staticmethod
    def execute(url: str) -> ToolResult:
        return ToolResult(
            "error",
            {"url": url, "attached": False},
            "No browser session attached; refusing unattached open",
        )


BROWSER_TOOLS = [BrowserOpenTool]
