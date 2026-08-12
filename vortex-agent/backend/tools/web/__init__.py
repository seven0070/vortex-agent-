"""Web capability — local knowledge search is real; live web is optional and honest."""
from ..base import ToolResult


class WebSearchTool:
    name = "web.search"
    description = "Search Vortex memory and knowledge graph (offline-safe, no fabricated hits)"
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}, "n": {"type": "integer", "default": 3}}, "required": ["query"]}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "web"

    @staticmethod
    def execute(query: str, n: int = 3) -> ToolResult:
        results = []
        try:
            from memory import Memory
            mem = Memory()
            hits = []
            if hasattr(mem, "recall"):
                hits = mem.recall(query, n=n) or []
            if hasattr(mem, "semantic") and len(hits) < n:
                hits.extend(mem.semantic.recall_facts(query, n=n) or [])
            for h in hits:
                if isinstance(h, dict):
                    text = h.get("text") or h.get("fact") or str(h.get("data") or h)
                    src = h.get("type") or h.get("source") or "memory"
                else:
                    text, src = str(h), "memory"
                text = str(text).strip()
                if text:
                    results.append({"title": src, "snippet": text[:240], "source": src})
                if len(results) >= n:
                    break
        except Exception as e:
            return ToolResult("error", {"query": query}, f"Local search failed: {e}")
        if not results:
            return ToolResult(
                "error",
                {"query": query, "results": []},
                "No local knowledge match and no live web index is configured",
            )
        return ToolResult("success", {"results": results, "query": query}, "Local knowledge search")


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
            req = urllib.request.Request(url, headers={"User-Agent": "Vortex/0.5"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()[:6000].decode("utf-8", errors="ignore")
                return ToolResult("success", {"content": data, "url": url}, "Fetched")
        except Exception as e:
            return ToolResult("error", {}, f"Fetch failed: {e}")


WEB_TOOLS = [WebSearchTool, WebFetchTool]
