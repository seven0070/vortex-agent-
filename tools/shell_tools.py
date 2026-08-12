"""Restricted terminal tool."""
from __future__ import annotations

import re
import subprocess

from vortex_constants import WORKSPACE, ensure_home
from .registry import registry

ensure_home()

_BLOCK = re.compile(
    r"\b(rm\s+-rf\s+/|mkfs|dd\s+if=|shutdown|reboot|passwd|useradd|chmod\s+777\s+/)\b",
    re.I,
)
_ALLOW = (
    "ls", "pwd", "whoami", "uname", "df", "du", "cat ", "head ", "tail ",
    "wc ", "echo ", "date", "python", "pip ", "git ", "find ", "grep ",
    "rg ", "file ", "stat ", "env", "printenv", "which ", "id", "uptime",
    "free", "ps ", "tree", "md5sum", "sha256sum", "sort", "uniq",
    "mkdir ", "touch ", "cp ", "mv ", "printf ", "curl ", "wget ",
)


def terminal(command: str, timeout: int = 15) -> dict:
    cmd = (command or "").strip()
    if not cmd:
        return {"status": "error", "error": "Empty command.", "data": {}}
    if _BLOCK.search(cmd):
        return {"status": "error", "error": "Command blocked by safety policy.", "data": {}}
    first = cmd.split("|")[0].strip()
    if not any(first == p.strip() or first.startswith(p) for p in _ALLOW):
        return {
            "status": "error",
            "error": f"Command not on allowlist: {first[:40]}",
            "data": {},
        }
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=min(int(timeout or 15), 30),
            cwd=str(WORKSPACE),
        )
        status = "success" if proc.returncode == 0 else "error"
        return {
            "status": status,
            "message": f"exit {proc.returncode}",
            "error": (proc.stderr or "")[:1500] if status == "error" else None,
            "data": {
                "stdout": (proc.stdout or "")[:4000],
                "stderr": (proc.stderr or "")[:1500],
                "code": proc.returncode,
            },
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Command timed out.", "data": {}}


registry.register(
    "terminal",
    "Run a short allowlisted shell command in the workspace.",
    {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer", "default": 15},
        },
        "required": ["command"],
    },
    terminal,
    toolsets=["shell", "core"],
    is_dangerous=True,
)
