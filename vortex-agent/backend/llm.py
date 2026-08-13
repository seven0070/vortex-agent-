"""
Vortex LLM layer — Phase 3.

Provider-agnostic chat completion with NO hard dependencies (stdlib urllib only),
so `pip install -r requirements.txt` is unchanged and the test suite stays offline.

Design rules:
  1. OFF BY DEFAULT. If no provider is configured, `LLM.available` is False and every
     caller falls back to the original deterministic behaviour. This keeps the frozen
     eval suite reproducible — an LLM must never silently change benchmark scores.
  2. Fail soft. Network/auth/timeout errors never raise into the agent loop; they are
     recorded and the caller degrades to its heuristic path.
  3. Provider-agnostic. OpenAI-compatible (OpenAI, OpenRouter, Together, vLLM, LM Studio),
     Anthropic, and Ollama share one interface — like `hermes model`, no code changes.

Configure with env vars:
    VORTEX_LLM_PROVIDER   openai | anthropic | ollama | none      (default: auto-detect)
    VORTEX_LLM_MODEL      model id                                 (default: per-provider)
    VORTEX_LLM_BASE_URL   override endpoint (OpenAI-compatible)
    VORTEX_LLM_API_KEY    api key (falls back to OPENAI_API_KEY / ANTHROPIC_API_KEY / OPENROUTER_API_KEY)
    VORTEX_LLM_TIMEOUT    seconds (default 30)
    VORTEX_LLM_MAX_TOKENS default 800
    VORTEX_LLM_TEMPERATURE default 0.3
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "ollama": "llama3.1",
}

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434/v1",
}


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def detect_provider() -> Optional[str]:
    """Pick a provider from the environment. Returns None when nothing is configured."""
    explicit = (_env("VORTEX_LLM_PROVIDER") or "").strip().lower()
    if explicit in ("none", "off", "disabled"):
        return None
    if explicit in DEFAULT_MODELS:
        return explicit
    if explicit:
        return explicit  # unknown provider name -> treated as OpenAI-compatible
    # auto-detect from well-known keys
    if _env("VORTEX_LLM_API_KEY") or _env("OPENAI_API_KEY") or _env("OPENROUTER_API_KEY"):
        return "openai"
    if _env("ANTHROPIC_API_KEY"):
        return "anthropic"
    if _env("OLLAMA_HOST"):
        return "ollama"
    return None


class LLMResult:
    """Outcome of one completion. Falsy when the call did not produce text."""

    __slots__ = ("text", "ok", "error", "latency_ms", "model", "provider")

    def __init__(self, text: str = "", ok: bool = False, error: str = "",
                 latency_ms: int = 0, model: str = "", provider: str = ""):
        self.text = text
        self.ok = ok
        self.error = error
        self.latency_ms = latency_ms
        self.model = model
        self.provider = provider

    def __bool__(self) -> bool:
        return bool(self.ok and self.text.strip())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text, "ok": self.ok, "error": self.error,
            "latency_ms": self.latency_ms, "model": self.model, "provider": self.provider,
        }


class LLM:
    """
    Minimal provider-agnostic chat client.

    `transport` is injectable purely so tests can run a deterministic fake without
    touching the network. Signature: transport(url, payload, headers) -> dict
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None,
                 api_key: Optional[str] = None, base_url: Optional[str] = None,
                 timeout: Optional[float] = None, transport=None):
        self.provider = (provider or detect_provider() or "").lower() or None
        self.transport = transport
        self.model = model or _env("VORTEX_LLM_MODEL") or DEFAULT_MODELS.get(self.provider or "", "")
        self.base_url = (base_url or _env("VORTEX_LLM_BASE_URL")
                         or DEFAULT_BASE_URLS.get(self.provider or "", "")).rstrip("/")
        self.api_key = api_key or self._resolve_key()
        self.timeout = float(timeout or _env("VORTEX_LLM_TIMEOUT", "30"))
        self.max_tokens = int(_env("VORTEX_LLM_MAX_TOKENS", "800"))
        self.temperature = float(_env("VORTEX_LLM_TEMPERATURE", "0.3"))
        # rolling telemetry
        self.calls = 0
        self.failures = 0
        self.total_latency_ms = 0
        self.last_error = ""

    def _resolve_key(self) -> str:
        if self.provider == "anthropic":
            return _env("VORTEX_LLM_API_KEY") or _env("ANTHROPIC_API_KEY") or ""
        if self.provider == "ollama":
            return _env("VORTEX_LLM_API_KEY") or "ollama"  # local, key unused
        return (_env("VORTEX_LLM_API_KEY") or _env("OPENAI_API_KEY")
                or _env("OPENROUTER_API_KEY") or "")

    @property
    def available(self) -> bool:
        """True only when a real completion could plausibly be made."""
        if self.transport is not None:
            return True  # injected (tests / custom backends)
        if not self.provider:
            return False
        if self.provider == "ollama":
            return bool(self.base_url)
        return bool(self.api_key and self.base_url and self.model)

    # ── public API ──
    def complete(self, system: str, user: str, temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None) -> LLMResult:
        """One-shot completion. Never raises."""
        return self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature, max_tokens=max_tokens,
        )

    def chat(self, messages: List[Dict[str, str]], temperature: Optional[float] = None,
             max_tokens: Optional[int] = None) -> LLMResult:
        if not self.available:
            return LLMResult(ok=False, error="llm_not_configured", provider=self.provider or "none")

        temp = self.temperature if temperature is None else temperature
        mt = self.max_tokens if max_tokens is None else max_tokens
        t0 = time.time()
        self.calls += 1
        try:
            if self.provider == "anthropic":
                url, payload, headers = self._anthropic_request(messages, temp, mt)
            else:
                url, payload, headers = self._openai_request(messages, temp, mt)

            raw = (self.transport(url, payload, headers) if self.transport
                   else self._http_post(url, payload, headers))
            text = self._extract_text(raw)
            ms = int((time.time() - t0) * 1000)
            self.total_latency_ms += ms
            if not text.strip():
                self.failures += 1
                self.last_error = "empty_response"
                return LLMResult(ok=False, error="empty_response", latency_ms=ms,
                                 model=self.model, provider=self.provider)
            return LLMResult(text=text.strip(), ok=True, latency_ms=ms,
                             model=self.model, provider=self.provider)
        except Exception as e:  # noqa: BLE001 — fail soft by contract
            ms = int((time.time() - t0) * 1000)
            self.failures += 1
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            self.total_latency_ms += ms
            return LLMResult(ok=False, error=self.last_error, latency_ms=ms,
                             model=self.model, provider=self.provider)

    def complete_json(self, system: str, user: str, temperature: float = 0.0) -> Optional[Any]:
        """Completion parsed as JSON. Returns None if unusable — callers must handle None."""
        r = self.complete(system + "\n\nRespond with ONLY valid JSON. No prose, no code fences.",
                          user, temperature=temperature)
        if not r:
            return None
        return extract_json(r.text)

    # ── provider request shapes ──
    def _openai_request(self, messages, temperature, max_tokens):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if "openrouter" in self.base_url:
            headers["HTTP-Referer"] = "https://github.com/seven0070/vortex-agent-"
            headers["X-Title"] = "Vortex Agent"
        payload = {
            "model": self.model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        }
        return f"{self.base_url}/chat/completions", payload, headers

    def _anthropic_request(self, messages, temperature, max_tokens):
        system = " ".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model, "messages": convo,
            "max_tokens": max_tokens, "temperature": temperature,
        }
        if system:
            payload["system"] = system
        return f"{self.base_url}/messages", payload, headers

    def _http_post(self, url: str, payload: dict, headers: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _extract_text(raw: dict) -> str:
        if not isinstance(raw, dict):
            return ""
        # OpenAI-compatible
        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") or {}
            if isinstance(msg, dict) and msg.get("content"):
                return str(msg["content"])
            if choices[0].get("text"):
                return str(choices[0]["text"])
        # Anthropic
        content = raw.get("content")
        if isinstance(content, list):
            return "".join(b.get("text", "") for b in content if isinstance(b, dict))
        return ""

    def status(self) -> Dict[str, Any]:
        avg = int(self.total_latency_ms / self.calls) if self.calls else 0
        return {
            "available": self.available,
            "provider": self.provider or "none",
            "model": self.model if self.available else "",
            "base_url": self.base_url if self.available else "",
            "calls": self.calls,
            "failures": self.failures,
            "avg_latency_ms": avg,
            "last_error": self.last_error,
            "mode": "live" if self.available else "deterministic-fallback",
        }


def extract_json(text: str) -> Optional[Any]:
    """Best-effort JSON out of a model reply (handles ```json fences and surrounding prose)."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1] if len(t.split("```")) > 1 else t
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
        t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        s, e = t.find(opener), t.rfind(closer)
        if s != -1 and e > s:
            try:
                return json.loads(t[s:e + 1])
            except Exception:
                continue
    return None


_SHARED: Optional[LLM] = None


def get_llm() -> LLM:
    """Process-wide shared client (so telemetry aggregates across subsystems)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = LLM()
    return _SHARED


def set_llm(llm: Optional[LLM]) -> None:
    """Swap the shared client — used by tests and by `/llm` reconfiguration."""
    global _SHARED
    _SHARED = llm


def reset_llm() -> None:
    set_llm(None)
