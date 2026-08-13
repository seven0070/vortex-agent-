"""REST API client for Vortex backend."""
from __future__ import annotations

from typing import Any

import requests


class VortexApiClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.session = requests.Session()
        self.timeout = timeout
        self.set_base_url(base_url)

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            timeout=kwargs.pop("timeout", self.timeout),
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def chat(self, message: str, orchestrated: bool = False) -> dict[str, Any]:
        return self._request("POST", "/api/chat", json={"message": message, "orchestrated": orchestrated})

    def stats(self) -> dict[str, Any]:
        return self._request("GET", "/api/stats")

    def memory(self, query: str = "", limit: int = 10) -> dict[str, Any]:
        return self._request("GET", "/api/memory", params={"query": query, "limit": limit})

    def memory_graph(self, limit: int = 40) -> dict[str, Any]:
        return self._request("GET", "/api/memory/graph", params={"limit": limit})

    def council(self) -> dict[str, Any]:
        return self._request("GET", "/api/council")

    def deliberate(self, goal: str) -> dict[str, Any]:
        return self._request("POST", "/api/council/deliberate", json={"message": goal})

    def governance(self) -> dict[str, Any]:
        return self._request("GET", "/api/governance")

    def governance_evaluate(self, task: str, action: str = "execute", agent: str = "chief", context: dict | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/governance/evaluate",
            json={"task": task, "action": action, "agent": agent, "context": context or {}},
        )

    def tools(self) -> dict[str, Any]:
        return self._request("GET", "/api/tools")

    def execute_tool(self, name: str, args: dict[str, Any], agent: str = "chief") -> dict[str, Any]:
        return self._request("POST", "/api/tools/exec", json={"name": name, "args": args, "agent": agent})

    def orchestration_list(self) -> Any:
        return self._request("GET", "/api/orchestration")

    def orchestration_run(self, goal: str) -> dict[str, Any]:
        return self._request("POST", "/api/orchestration/run", json={"message": goal})

    def benchmark(self) -> dict[str, Any]:
        return self._request("POST", "/api/rsi/eval/benchmark")

    def observability(self) -> dict[str, Any]:
        return self._request("GET", "/api/observability")
