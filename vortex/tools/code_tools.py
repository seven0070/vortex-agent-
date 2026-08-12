"""Code execution + calculator."""
from __future__ import annotations

import ast
import math
import os
import re
import subprocess
import sys
import tempfile

from vortex.constants import WORKSPACE, ensure_home
from .registry import registry

ensure_home()

_SAFE = {
    "abs": abs, "round": round, "min": min, "max": max, "pow": pow,
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "pi": math.pi, "e": math.e,
}


def execute_code(code: str, timeout: int = 10) -> dict:
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {"status": "error", "error": f"Syntax error: {e}", "data": {}}
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
            return {
                "status": "success",
                "message": "Code executed.",
                "data": {"output": (proc.stdout or "")[:4000]},
            }
        return {
            "status": "error",
            "error": f"Exit code {proc.returncode}.",
            "data": {"stderr": (proc.stderr or "")[:2000]},
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"Timed out after {timeout}s.", "data": {}}
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def calculator(expression: str) -> dict:
    expr = (expression or "").replace("^", "**").strip()
    if not re.fullmatch(r"[0-9a-zA-Z_+\-*/%().\s,]+", expr):
        return {"status": "error", "error": "Unsafe characters in expression.", "data": {}}
    try:
        value = eval(expr, {"__builtins__": {}}, _SAFE)  # noqa: S307
        return {
            "status": "success",
            "message": f"Result = {value}",
            "data": {"expression": expr, "result": value},
        }
    except Exception as e:
        return {"status": "error", "error": f"Math error: {e}", "data": {}}


registry.register(
    "execute_code",
    "Execute Python code in an isolated subprocess with a timeout.",
    {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "timeout": {"type": "integer", "default": 10},
        },
        "required": ["code"],
    },
    execute_code,
    toolsets=["code", "core"],
)

registry.register(
    "calculator",
    "Safely evaluate a math expression.",
    {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
    calculator,
    toolsets=["code", "core"],
)
