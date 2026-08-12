"""Web capability"""
import json
from ..base import ToolResult

class WebSearchTool:
    name = "web.search"
    description = "Search memory / local knowledge (mock web search, offline-safe)"
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}, "n": {"type": "integer", "default": 3}}, "required": ["query"]}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "web"
    @staticmethod
    def execute(query: str, n: int = 3) -> ToolResult:
        # offline fallback: we don't do real web, but search memory would be injected by orchestrator
        # For now mock with heuristics
        return ToolResult("success", {"results": [{"title": f"Result for {query}", "snippet": f"Mock result {i} for {query}"} for i in range(n)], "query": query}, "Web search (mock)")

class WebFetchTool:
    name = "web.fetch"
    description = "Fetch a URL (safe, timeout)"
    input_schema = {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    permissions = ["read", "network"]
    risk_level = "medium"
    timeout = 10
    category = "web"
    @staticmethod
    def execute(url: str) -> ToolResult:
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "Vortex/0.4"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()[:6000].decode('utf-8', errors='ignore')
                return ToolResult("success", {"content": data, "url": url}, "Fetched")
        except Exception as e:
            return ToolResult("error", {}, f"Fetch failed: {e}")

WEB_TOOLS = [WebSearchTool, WebFetchTool]
