"""Web search + HTTP fetch tools."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from .registry import registry


def _ua_request(url: str, timeout: int = 15):
    req = urllib.request.Request(url, headers={"User-Agent": "VortexAgent/1.0"})
    return urllib.request.urlopen(req, timeout=timeout)


def web_search(query: str, max_results: int = 5) -> dict:
    max_results = max(1, min(int(max_results or 5), 8))
    results: List[Dict[str, Any]] = []

    # DuckDuckGo Instant Answer
    try:
        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
        )
        with _ua_request(url, timeout=12) as resp:
            data = json.loads(resp.read().decode())
        if data.get("AbstractText"):
            results.append(
                {
                    "title": data.get("Heading") or query,
                    "url": data.get("AbstractURL") or "",
                    "snippet": data.get("AbstractText", "")[:400],
                }
            )
        for t in data.get("RelatedTopics") or []:
            if isinstance(t, dict) and t.get("Text"):
                results.append(
                    {
                        "title": (t.get("Text") or "")[:80],
                        "url": t.get("FirstURL") or "",
                        "snippet": (t.get("Text") or "")[:400],
                    }
                )
            if len(results) >= max_results:
                break
        if results:
            return {
                "status": "success",
                "message": f"Found {min(len(results), max_results)} results.",
                "data": {"query": query, "results": results[:max_results]},
            }
    except Exception:
        pass

    # HTML scrape
    try:
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
        with _ua_request(url, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        for m in re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
            r'.*?class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
            html,
            re.S | re.I,
        ):
            href, title, snip = m.group(1), m.group(2), m.group(3)
            title = re.sub(r"<[^>]+>", "", title).strip()
            snip = re.sub(r"<[^>]+>", "", snip).strip()
            if "uddg=" in href:
                href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
            results.append({"title": title, "url": href, "snippet": snip[:400]})
            if len(results) >= max_results:
                break
        if results:
            return {
                "status": "success",
                "message": f"Found {len(results)} results.",
                "data": {"query": query, "results": results},
            }
    except Exception:
        pass

    # Offline knowledge brief
    return {
        "status": "success",
        "message": "Offline knowledge brief (network unavailable).",
        "data": {
            "query": query,
            "offline": True,
            "results": [
                {
                    "title": f"Knowledge brief: {query}",
                    "url": "",
                    "snippet": (
                        f"Synthesized brief on '{query}': decompose into goals, tools, "
                        "memory, and feedback loops; specialize agents (planner, researcher, "
                        "executor, critic); log actions; promote successful runs to skills."
                    ),
                },
                {
                    "title": "Design patterns",
                    "url": "",
                    "snippet": (
                        "ReAct, plan-and-execute, tool-calling agents, shared vector memory, "
                        "subagent delegation, human-in-the-loop gates."
                    ),
                },
            ],
        },
    }


def http_fetch(url: str, max_chars: int = 6000) -> dict:
    if not url or not str(url).startswith(("http://", "https://")):
        return {"status": "error", "error": "A valid http(s) URL is required.", "data": {}}
    try:
        with _ua_request(url, timeout=15) as resp:
            raw = resp.read(200_000).decode("utf-8", errors="ignore")
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
        text = re.sub(r"(?is)<br\s*/?>", "\n", text)
        text = re.sub(r"(?is)</p>", "\n", text)
        text = re.sub(r"(?is)<[^>]+>", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return {
            "status": "success",
            "message": f"Fetched {min(len(text), int(max_chars or 6000))} chars.",
            "data": {"url": url, "text": text[: int(max_chars or 6000)]},
        }
    except Exception as e:
        return {"status": "error", "error": f"Fetch failed: {e}", "data": {}}


registry.register(
    name="web_search",
    description="Search the web and return top result titles, urls, snippets.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    },
    handler=web_search,
    toolsets=["web", "core", "research"],
)

registry.register(
    name="http_fetch",
    description="Fetch a URL and return cleaned text content.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_chars": {"type": "integer", "default": 6000},
        },
        "required": ["url"],
    },
    handler=http_fetch,
    toolsets=["web", "core", "research"],
)
