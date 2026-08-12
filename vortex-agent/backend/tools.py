"""Vortex Agent — tool belt for the autonomous loop."""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

WORKSPACE = Path.home() / ".vortex" / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

# Safety: shell allowlist (no network-destructive / privilege ops)
_SHELL_BLOCK = re.compile(
    r"\b(rm\s+-rf\s+/|mkfs|dd\s+if=|shutdown|reboot|passwd|useradd|chmod\s+777\s+/)\b",
    re.I,
)


@dataclass
class ToolResult:
    status: str
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self):
        return {"status": self.status, "data": self.data, "message": self.message}

    def observation(self) -> str:
        if self.status != "success":
            return f"ERROR ({self.message}): {json.dumps(self.data)[:800]}"
        payload = json.dumps(self.data, default=str)
        if len(payload) > 2500:
            payload = payload[:2500] + "…"
        return f"OK — {self.message} | data={payload}"


# ─── Glossopetrae ──────────────────────────────────────────────────────────
class GlossopetraeTool:
    name = "glossopetrae"
    description = "Translate text into a procedurally generated conlang and optionally render SVG."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "seed": {"type": "integer", "default": 42},
            "render_svg": {"type": "boolean", "default": True},
        },
        "required": ["text"],
    }

    @staticmethod
    def execute(text: str, seed: int = 42, render_svg: bool = True) -> ToolResult:
        random.seed(seed)
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        shuffled = list(alphabet)
        random.shuffle(shuffled)
        cipher = dict(zip(alphabet, shuffled))
        translated = "".join(cipher.get(c, c) for c in text.lower())
        svg = ""
        if render_svg:
            safe = (
                translated.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="60">'
                '<rect width="420" height="60" fill="#0a0a0a"/>'
                f'<text x="12" y="36" font-family="monospace" font-size="16" '
                f'fill="#f97316">{safe}</text></svg>'
            )
        return ToolResult(
            "success",
            {"translated": translated, "seed": seed, "svg": svg},
            f"Translated with seed {seed}.",
        )


# ─── Steganography ─────────────────────────────────────────────────────────
class SteganographyTool:
    name = "steganography"
    description = "Encode/decode a secret payload inside benign cover text."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["encode", "decode"]},
            "cover": {"type": "string"},
            "payload": {"type": "string"},
            "stego": {"type": "string"},
            "method": {
                "type": "string",
                "enum": ["marker", "whitespace", "unicode"],
                "default": "marker",
            },
        },
        "required": ["action"],
    }

    @staticmethod
    def execute(
        action: str,
        cover: str = "",
        payload: str = "",
        stego: str = "",
        method: str = "marker",
    ) -> ToolResult:
        if action == "encode":
            if not payload:
                return ToolResult("error", {}, "payload required for encode")
            cover = cover or "The weather is quite pleasant today."
            if method == "marker":
                tag = hashlib.md5(payload.encode()).hexdigest()[:12]
                encoded = f"{cover}\n<!--STEGO:{tag}-->{payload}<!--/STEGO-->"
            else:
                # zero-width join encoding
                bits = "".join(f"{ord(c):08b}" for c in payload)
                zw = "".join("\u200b" if b == "0" else "\u200c" for b in bits)
                encoded = f"{cover}{zw}"
            return ToolResult(
                "success",
                {"encoded": encoded, "method": method},
                f"Payload hidden via {method}.",
            )

        if action == "decode":
            if not stego:
                return ToolResult("error", {}, "stego text required for decode")
            if "<!--STEGO:" in stego:
                try:
                    decoded = (
                        stego.split("<!--STEGO:")[1]
                        .split("-->")[1]
                        .split("<!--/STEGO-->")[0]
                    )
                    return ToolResult(
                        "success", {"decoded": decoded}, "Payload extracted (marker)."
                    )
                except IndexError:
                    return ToolResult("error", {}, "Malformed marker payload.")
            # try zero-width
            bits = "".join(
                "0" if c == "\u200b" else "1" if c == "\u200c" else "" for c in stego
            )
            if bits and len(bits) >= 8:
                chars = [
                    chr(int(bits[i : i + 8], 2)) for i in range(0, len(bits) - 7, 8)
                ]
                return ToolResult(
                    "success",
                    {"decoded": "".join(chars)},
                    "Payload extracted (unicode zw).",
                )
            return ToolResult("error", {}, "No hidden payload detected.")

        return ToolResult("error", {}, f"Invalid action: {action}")


# ─── CodeForge ─────────────────────────────────────────────────────────────
class CodeForgeTool:
    name = "codeforge"
    description = "Execute Python code in an isolated subprocess with a timeout."
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "timeout": {"type": "integer", "default": 10},
        },
        "required": ["code"],
    }

    @staticmethod
    def execute(code: str, timeout: int = 10) -> ToolResult:
        try:
            ast.parse(code)
        except SyntaxError as e:
            return ToolResult("error", {}, f"Syntax error: {e}")

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=str(WORKSPACE)
        )
        try:
            tmp.write(code)
            tmp.close()
            proc = subprocess.run(
                [sys.executable, "-I", tmp.name],
                capture_output=True,
                text=True,
                timeout=min(int(timeout or 10), 30),
                cwd=str(WORKSPACE),
            )
            if proc.returncode == 0:
                return ToolResult(
                    "success", {"output": proc.stdout[:4000]}, "Code executed."
                )
            return ToolResult(
                "error",
                {"stderr": proc.stderr[:2000]},
                f"Exit code {proc.returncode}.",
            )
        except subprocess.TimeoutExpired:
            return ToolResult("error", {}, f"Timed out after {timeout}s.")
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


# ─── Calculator ────────────────────────────────────────────────────────────
class CalculatorTool:
    name = "calculator"
    description = "Safely evaluate a math expression (arithmetic, powers, sqrt, etc.)."
    parameters = {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    }

    _SAFE = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "pi": math.pi,
        "e": math.e,
    }

    @classmethod
    def execute(cls, expression: str) -> ToolResult:
        expr = expression.replace("^", "**").strip()
        if not re.fullmatch(r"[0-9a-zA-Z_+\-*/%().\s,]+", expr):
            return ToolResult("error", {}, "Expression contains unsafe characters.")
        try:
            value = eval(expr, {"__builtins__": {}}, cls._SAFE)  # noqa: S307 — sandboxed
            return ToolResult(
                "success", {"expression": expr, "result": value}, f"Result = {value}"
            )
        except Exception as e:
            return ToolResult("error", {}, f"Math error: {e}")


# ─── Web search (DuckDuckGo HTML, no key) ──────────────────────────────────
class WebSearchTool:
    name = "web_search"
    description = "Search the web (DuckDuckGo) and return top result titles, urls, snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    }

    @staticmethod
    def execute(query: str, max_results: int = 5) -> ToolResult:
        max_results = max(1, min(int(max_results or 5), 8))
        # 1) try duckduckgo instant answer API
        try:
            url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
                {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
            )
            req = urllib.request.Request(
                url, headers={"User-Agent": "VortexAgent/1.0"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())
            results = []
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
                return ToolResult(
                    "success",
                    {"query": query, "results": results[:max_results]},
                    f"Found {min(len(results), max_results)} results.",
                )
        except Exception:
            pass

        # 2) HTML scrape fallback
        try:
            url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
                {"q": query}
            )
            req = urllib.request.Request(
                url, headers={"User-Agent": "VortexAgent/1.0 (research bot)"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            results = []
            for m in re.finditer(
                r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
                r'.*?class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
                html,
                re.S | re.I,
            ):
                href, title, snip = m.group(1), m.group(2), m.group(3)
                title = re.sub(r"<[^>]+>", "", title).strip()
                snip = re.sub(r"<[^>]+>", "", snip).strip()
                # unwrap ddg redirect
                if "uddg=" in href:
                    href = urllib.parse.unquote(
                        href.split("uddg=")[1].split("&")[0]
                    )
                results.append({"title": title, "url": href, "snippet": snip[:400]})
                if len(results) >= max_results:
                    break
            if results:
                return ToolResult(
                    "success",
                    {"query": query, "results": results},
                    f"Found {len(results)} results.",
                )
        except Exception:
            pass

        # 3) offline knowledge stub so the agent can still complete missions
        return ToolResult(
            "success",
            {
                "query": query,
                "results": [
                    {
                        "title": f"Knowledge brief: {query}",
                        "url": "",
                        "snippet": (
                            f"Live web search unavailable. Synthesized brief on '{query}': "
                            "break the problem into goals, tools, memory, and feedback loops; "
                            "prefer multi-agent specialization (planner, researcher, executor, critic); "
                            "log every action; persist skills from successful runs."
                        ),
                    },
                    {
                        "title": "Design patterns",
                        "url": "",
                        "snippet": (
                            "ReAct (reason+act), plan-and-execute, tool-calling agents, "
                            "shared vector memory, and human-in-the-loop approval gates."
                        ),
                    },
                ],
                "offline": True,
            },
            "Offline knowledge brief (network unavailable).",
        )


# ─── HTTP fetch ────────────────────────────────────────────────────────────
class HttpFetchTool:
    name = "http_fetch"
    description = "Fetch a URL and return cleaned text content (max ~8KB)."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_chars": {"type": "integer", "default": 6000},
        },
        "required": ["url"],
    }

    @staticmethod
    def execute(url: str, max_chars: int = 6000, **_kw) -> ToolResult:
        if not url or not url.startswith(("http://", "https://")):
            return ToolResult(
                "error",
                {},
                "A valid http(s) URL is required. Skip if none available.",
            )
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "VortexAgent/1.0 (research bot)"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read(200_000).decode("utf-8", errors="ignore")
            # crude HTML → text
            text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
            text = re.sub(r"(?is)<br\s*/?>", "\n", text)
            text = re.sub(r"(?is)</p>", "\n", text)
            text = re.sub(r"(?is)<[^>]+>", " ", text)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            return ToolResult(
                "success",
                {"url": url, "text": text[: int(max_chars or 6000)]},
                f"Fetched {min(len(text), int(max_chars or 6000))} chars.",
            )
        except Exception as e:
            return ToolResult("error", {}, f"Fetch failed: {e}")


# ─── Filesystem (sandboxed to WORKSPACE) ───────────────────────────────────
def _safe_path(path: str) -> Path:
    p = (WORKSPACE / path).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise ValueError("Path escapes workspace")
    return p


class WriteFileTool:
    name = "write_file"
    description = "Write text to a file inside the Vortex workspace (~/.vortex/workspace)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    @staticmethod
    def execute(path: str, content: str, **_kw) -> ToolResult:
        try:
            p = _safe_path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(
                "success",
                {"path": str(p), "bytes": len(content.encode())},
                f"Wrote {path}",
            )
        except Exception as e:
            return ToolResult("error", {}, str(e))


class ReadFileTool:
    name = "read_file"
    description = "Read a text file from the Vortex workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "max_chars": {"type": "integer", "default": 8000},
        },
        "required": ["path"],
    }

    @staticmethod
    def execute(path: str, max_chars: int = 8000) -> ToolResult:
        try:
            p = _safe_path(path)
            if not p.exists():
                return ToolResult("error", {}, f"Not found: {path}")
            text = p.read_text(encoding="utf-8", errors="replace")
            return ToolResult(
                "success",
                {"path": str(p), "content": text[: int(max_chars or 8000)]},
                f"Read {path}",
            )
        except Exception as e:
            return ToolResult("error", {}, str(e))


class ListFilesTool:
    name = "list_files"
    description = "List files under a workspace path."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "glob": {"type": "string", "default": "**/*"},
        },
        "required": [],
    }

    @staticmethod
    def execute(path: str = ".", glob: str = "**/*") -> ToolResult:
        try:
            root = _safe_path(path or ".")
            if not root.exists():
                return ToolResult("error", {}, f"Not found: {path}")
            files = []
            for f in sorted(root.glob(glob or "**/*")):
                if f.is_file():
                    rel = str(f.relative_to(WORKSPACE))
                    files.append(
                        {"path": rel, "size": f.stat().st_size}
                    )
                if len(files) >= 100:
                    break
            return ToolResult(
                "success",
                {"root": str(root), "files": files},
                f"{len(files)} files.",
            )
        except Exception as e:
            return ToolResult("error", {}, str(e))


# ─── Shell (restricted) ────────────────────────────────────────────────────
class ShellTool:
    name = "shell"
    description = "Run a short allowlisted shell command in the workspace (read-only friendly)."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer", "default": 15},
        },
        "required": ["command"],
    }

    @staticmethod
    def execute(command: str, timeout: int = 15) -> ToolResult:
        cmd = (command or "").strip()
        if not cmd:
            return ToolResult("error", {}, "Empty command.")
        if _SHELL_BLOCK.search(cmd):
            return ToolResult("error", {}, "Command blocked by safety policy.")
        # soft allowlist prefixes
        allowed_prefixes = (
            "ls",
            "pwd",
            "whoami",
            "uname",
            "df",
            "du",
            "cat ",
            "head ",
            "tail ",
            "wc ",
            "echo ",
            "date",
            "python",
            "pip ",
            "git ",
            "find ",
            "grep ",
            "rg ",
            "file ",
            "stat ",
            "env",
            "printenv",
            "which ",
            "id",
            "uptime",
            "free",
            "ps ",
            "tree",
            "md5sum",
            "sha256sum",
            "sort",
            "uniq",
            "mkdir ",
            "touch ",
            "cp ",
            "mv ",
            "printf ",
        )
        first = cmd.split("|")[0].strip()
        if not any(first == p.strip() or first.startswith(p) for p in allowed_prefixes):
            return ToolResult(
                "error",
                {},
                f"Command not on allowlist. First token group: {first[:40]}",
            )
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=min(int(timeout or 15), 30),
                cwd=str(WORKSPACE),
            )
            out = (proc.stdout or "")[:4000]
            err = (proc.stderr or "")[:1500]
            status = "success" if proc.returncode == 0 else "error"
            return ToolResult(
                status,
                {"stdout": out, "stderr": err, "code": proc.returncode},
                f"exit {proc.returncode}",
            )
        except subprocess.TimeoutExpired:
            return ToolResult("error", {}, "Command timed out.")
        except Exception as e:
            return ToolResult("error", {}, str(e))


# ─── Memory tools (bound at runtime) ───────────────────────────────────────
class RememberTool:
    name = "remember"
    description = "Store a fact/finding in long-term vector memory."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "tag": {"type": "string", "default": "note"},
        },
        "required": ["text"],
    }

    def __init__(self, vector=None):
        self.vector = vector

    def execute(self, text: str, tag: str = "note", **_kw) -> ToolResult:
        if not text:
            return ToolResult("error", {}, "text required")
        if self.vector is not None:
            self.vector.remember(text, {"tag": tag or "note"})
        return ToolResult(
            "success", {"stored": text[:200], "tag": tag}, "Remembered."
        )


class RecallTool:
    name = "recall"
    description = "Search long-term vector memory for related notes."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "n": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    }

    def __init__(self, vector=None):
        self.vector = vector

    def execute(self, query: str, n: int = 5) -> ToolResult:
        hits = self.vector.recall(query, n=int(n or 5)) if self.vector else []
        return ToolResult(
            "success", {"hits": hits}, f"{len(hits)} memories recalled."
        )


class NowTool:
    name = "now"
    description = "Return the current local date and time."
    parameters = {"type": "object", "properties": {}, "required": []}

    @staticmethod
    def execute() -> ToolResult:
        dt = datetime.now()
        return ToolResult(
            "success",
            {
                "iso": dt.isoformat(timespec="seconds"),
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M:%S"),
                "weekday": dt.strftime("%A"),
            },
            "Current time.",
        )


# Base tool classes (no runtime deps)
TOOL_CLASSES: List[type] = [
    GlossopetraeTool,
    SteganographyTool,
    CodeForgeTool,
    CalculatorTool,
    WebSearchTool,
    HttpFetchTool,
    WriteFileTool,
    ReadFileTool,
    ListFilesTool,
    ShellTool,
    NowTool,
]


def build_toolbelt(vector=None, memory=None) -> Dict[str, Any]:
    """Instantiate tools, wiring memory-backed ones."""
    tools: Dict[str, Any] = {}
    for cls in TOOL_CLASSES:
        tools[cls.name] = cls()
    tools["remember"] = RememberTool(vector=vector)
    tools["recall"] = RecallTool(vector=vector)
    return tools


def tools_description(tools: Dict[str, Any]) -> str:
    lines = []
    for name, t in tools.items():
        params = getattr(t, "parameters", {}) or {}
        props = list((params.get("properties") or {}).keys())
        desc = getattr(t, "description", "")
        lines.append(f"- {name}({', '.join(props)}): {desc}")
    return "\n".join(lines)


def run_tool(tools: Dict[str, Any], name: str, args: dict) -> ToolResult:
    tool = tools.get(name)
    if not tool:
        return ToolResult("error", {}, f"Unknown tool: {name}")
    args = args or {}
    # filter unexpected kwargs softly
    try:
        return tool.execute(**args)
    except TypeError:
        # drop unknown keys
        import inspect

        sig = inspect.signature(tool.execute)
        accepted = {
            k: v
            for k, v in args.items()
            if k in sig.parameters
            or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        }
        try:
            return tool.execute(**accepted)
        except Exception as e:
            return ToolResult("error", {}, f"Tool crashed: {e}")
    except Exception as e:
        return ToolResult("error", {}, f"Tool crashed: {e}")
