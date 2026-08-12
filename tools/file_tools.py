"""Workspace file tools — sandboxed to VORTEX workspace."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from vortex_constants import WORKSPACE, ensure_home
from .registry import registry

ensure_home()


def _safe(path: str) -> Path:
    p = (WORKSPACE / (path or ".")).resolve()
    root = WORKSPACE.resolve()
    if not str(p).startswith(str(root)):
        raise ValueError("Path escapes workspace")
    return p


def write_file(path: str, content: str) -> dict:
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content or "", encoding="utf-8")
    return {
        "status": "success",
        "message": f"Wrote {path}",
        "data": {"path": str(p), "bytes": len((content or "").encode())},
    }


def read_file(path: str, max_chars: int = 8000) -> dict:
    p = _safe(path)
    if not p.exists():
        return {"status": "error", "error": f"Not found: {path}", "data": {}}
    text = p.read_text(encoding="utf-8", errors="replace")
    return {
        "status": "success",
        "message": f"Read {path}",
        "data": {"path": str(p), "content": text[: int(max_chars or 8000)]},
    }


def list_files(path: str = ".", glob: str = "**/*") -> dict:
    root = _safe(path or ".")
    if not root.exists():
        return {"status": "error", "error": f"Not found: {path}", "data": {}}
    files = []
    for f in sorted(root.glob(glob or "**/*")):
        if f.is_file():
            files.append({"path": str(f.relative_to(WORKSPACE)), "size": f.stat().st_size})
        if len(files) >= 100:
            break
    return {
        "status": "success",
        "message": f"{len(files)} files.",
        "data": {"root": str(root), "files": files},
    }


def search_files(pattern: str, path: str = ".", max_hits: int = 30) -> dict:
    root = _safe(path or ".")
    rx = re.compile(pattern, re.I)
    hits = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in {
            ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
            ".js", ".ts", ".css", ".html", ".sh", ".rs", ".go",
        }:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(
                    {
                        "path": str(f.relative_to(WORKSPACE)),
                        "line": i,
                        "text": line.strip()[:200],
                    }
                )
                if len(hits) >= int(max_hits or 30):
                    return {
                        "status": "success",
                        "message": f"{len(hits)} hits (capped).",
                        "data": {"hits": hits},
                    }
    return {
        "status": "success",
        "message": f"{len(hits)} hits.",
        "data": {"hits": hits},
    }


registry.register(
    "write_file",
    "Write text to a file inside the Vortex workspace.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
    write_file,
    toolsets=["files", "core"],
)

registry.register(
    "read_file",
    "Read a text file from the Vortex workspace.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "max_chars": {"type": "integer", "default": 8000},
        },
        "required": ["path"],
    },
    read_file,
    toolsets=["files", "core"],
)

registry.register(
    "list_files",
    "List files under a workspace path.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "glob": {"type": "string", "default": "**/*"},
        },
    },
    list_files,
    toolsets=["files", "core"],
)

registry.register(
    "search_files",
    "Regex search across workspace text files.",
    {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."},
            "max_hits": {"type": "integer", "default": 30},
        },
        "required": ["pattern"],
    },
    search_files,
    toolsets=["files", "core"],
)
