"""Legacy tools from original tools.py — wrapped as capabilities."""
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

from paths import vortex_home
from .base import ToolResult

WORKSPACE = vortex_home() / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

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
    input_schema = parameters
    output_schema = {"type": "object", "properties": {"translated": {"type": "string"}, "svg": {"type": "string"}}}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "communication"
    rollback_method = None

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
    input_schema = parameters
    output_schema = {"type": "object"}
    permissions = ["read", "write"]
    risk_level = "medium"
    timeout = 5
    category = "security"
    rollback_method = "delete_last_stego"

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
    input_schema = parameters
    output_schema = {"type": "object", "properties": {"output": {"type": "string"}}}
    permissions = ["execute", "write"]
    risk_level = "high"
    timeout = 15
    category = "code"
    rollback_method = "kill_subprocess"

    @staticmethod
    def execute(code: str, timeout: int = 10) -> ToolResult:
        try:
            ast.parse(code)
        except SyntaxError as e:
            return ToolResult("error", {}, f"Syntax error: {e}")

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
