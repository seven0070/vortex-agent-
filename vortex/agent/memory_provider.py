"""Builtin memory provider — MEMORY.md style durable notes (Hermes pattern)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from vortex.constants import MEMORY_DIR, ensure_home


class BuiltinMemory:
    name = "builtin"

    def __init__(self):
        ensure_home()
        self.path = MEMORY_DIR / "MEMORY.md"
        if not self.path.exists():
            self.path.write_text(
                "# Vortex Memory\n\nDurable notes the agent keeps across sessions.\n\n",
                encoding="utf-8",
            )

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str = "", **kwargs) -> None:
        self.session_id = session_id

    def system_prompt_block(self, max_chars: int = 1500) -> str:
        text = self.path.read_text(encoding="utf-8", errors="replace")
        body = text.strip()
        if len(body) > max_chars:
            body = body[:max_chars] + "\n…"
        return f"## Long-term memory\n{body}"

    def write(self, text: str, tag: str = "note") -> None:
        ts = datetime.now().isoformat(timespec="seconds")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"\n### [{tag}] {ts}\n{text.strip()}\n")

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace")

    def prefetch(self, query: str) -> List[str]:
        # simple keyword filter over MEMORY.md sections
        text = self.read()
        q = (query or "").lower().split()
        hits = []
        for block in text.split("\n### "):
            low = block.lower()
            if any(t in low for t in q if len(t) > 3):
                hits.append(block[:300])
        return hits[:3]
