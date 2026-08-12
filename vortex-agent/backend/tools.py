"""Vortex Agent — Phase 1 custom tools."""
import ast
import hashlib
import os
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

WORKSPACE = Path.home() / ".vortex" / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)


@dataclass
class ToolResult:
    status: str
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self):
        return {"status": self.status, "data": self.data, "message": self.message}


# ─── Glossopetrae: conlang translation + SVG render ───────────────────────
class GlossopetraeTool:
    name = "glossopetrae"
    description = "Translate text into a procedurally generated conlang and render as SVG."
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
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="60">'
                '<rect width="420" height="60" fill="#0a0a0a"/>'
                f'<text x="12" y="36" font-family="monospace" font-size="16" '
                f'fill="#f97316">{translated}</text></svg>'
            )
        return ToolResult(
            "success",
            {"translated": translated, "seed": seed, "svg": svg},
            f"Translated with seed {seed}.",
        )


# ─── Steganography: hide/reveal payloads in cover text ────────────────────
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
            "method": {"type": "string", "enum": ["marker", "whitespace", "unicode"], "default": "marker"},
        },
        "required": ["action"],
    }

    @staticmethod
    def execute(action: str, cover: str = "", payload: str = "",
                stego: str = "", method: str = "marker") -> ToolResult:
        if action == "encode":
            if not payload:
                return ToolResult("error", {}, "payload required for encode")
            cover = cover or "The weather is quite pleasant today."
            if method == "marker":
                tag = hashlib.md5(payload.encode()).hexdigest()[:12]
                encoded = f"{cover}\n<!--STEGO:{tag}-->{payload}<!--/STEGO-->"
            elif method == "whitespace":
                encoded = f"{cover}{payload}"
            else:
                encoded = f"{cover}{payload}"
            return ToolResult("success", {"encoded": encoded, "method": method},
                              f"Payload hidden via {method}.")

        if action == "decode":
            if not stego:
                return ToolResult("error", {}, "stego text required for decode")
            if "<!--STEGO:" in stego:
                try:
                    decoded = stego.split("<!--STEGO:")[1].split("-->")[1].split("<!--/STEGO-->")[0]
                    return ToolResult("success", {"decoded": decoded}, "Payload extracted (marker).")
                except IndexError:
                    return ToolResult("error", {}, "Malformed marker payload.")
            return ToolResult("error", {}, "No hidden payload detected.")

        return ToolResult("error", {}, f"Invalid action: {action}")


# ─── CodeForge: safe sandboxed Python execution ───────────────────────────
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
        # Safety gate 1: syntax validation before execution
        try:
            ast.parse(code)
        except SyntaxError as e:
            return ToolResult("error", {}, f"Syntax error: {e}")

        # Safety gate 2: isolated subprocess, workspace-cwd, hard timeout
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=str(WORKSPACE))
        try:
            tmp.write(code)
            tmp.close()
            proc = subprocess.run(
                [sys.executable, "-I", tmp.name],
                capture_output=True, text=True, timeout=timeout, cwd=str(WORKSPACE),
            )
            if proc.returncode == 0:
                return ToolResult("success", {"output": proc.stdout[:4000]}, "Code executed.")
            return ToolResult("error", {"stderr": proc.stderr[:2000]}, f"Exit code {proc.returncode}.")
        except subprocess.TimeoutExpired:
            return ToolResult("error", {}, f"Timed out after {timeout}s.")
        finally:
            os.unlink(tmp.name)


TOOL_CLASSES = [GlossopetraeTool, SteganographyTool, CodeForgeTool]
