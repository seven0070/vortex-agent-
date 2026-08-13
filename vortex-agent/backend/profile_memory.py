"""
Vortex profile memory — MEMORY.md + USER.md (Hermes Tier-1 equivalent).

Vortex already had vector recall and a knowledge graph, but everything was
*probabilistic*: a fact only reached the agent if retrieval happened to surface it.
Hermes's insight is that a small set of durable facts should be **guaranteed context**,
loaded every single turn with zero retrieval latency.

Two human-readable files in VORTEX_HOME (editable by hand, like Hermes):
    MEMORY.md — durable facts, conventions, environment quirks, lessons
    USER.md   — who the user is: name, role, preferences, timezone

Both are size-capped. That cap is the whole point: an unbounded "always in context"
file silently becomes a prompt-bloat bug, so writes evict the oldest entries instead
of growing without limit.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from paths import vortex_home

MEMORY_CAP = 2200   # chars, matching Hermes' documented Tier-1 budget
USER_CAP = 1375

MEMORY_HEADER = "# MEMORY.md — durable facts Vortex should always know\n\n"
USER_HEADER = "# USER.md — who Vortex is working with\n\n"


class ProfileMemory:
    """Guaranteed-context facts. Always loaded, never retrieved."""

    def __init__(self, home=None):
        self.home = home or vortex_home()
        self.memory_path = self.home / "MEMORY.md"
        self.user_path = self.home / "USER.md"
        for p, h in ((self.memory_path, MEMORY_HEADER), (self.user_path, USER_HEADER)):
            if not p.exists():
                p.write_text(h)

    # ── read ──
    def _entries(self, path) -> List[str]:
        try:
            text = path.read_text()
        except Exception:
            return []
        return [ln[2:].strip() for ln in text.splitlines()
                if ln.startswith("- ") and ln[2:].strip()]

    def memory_entries(self) -> List[str]:
        return self._entries(self.memory_path)

    def user_entries(self) -> List[str]:
        return self._entries(self.user_path)

    def read_memory(self) -> str:
        try:
            return self.memory_path.read_text()
        except Exception:
            return MEMORY_HEADER

    def read_user(self) -> str:
        try:
            return self.user_path.read_text()
        except Exception:
            return USER_HEADER

    # ── write ──
    def _append(self, path, header: str, cap: int, entry: str) -> Dict[str, Any]:
        entry = " ".join(entry.split()).strip(" -")
        if not entry:
            return {"written": False, "reason": "empty"}
        entries = self._entries(path)
        # dedupe (case-insensitive, ignores trailing punctuation)
        norm = entry.lower().rstrip(".")
        if any(e.lower().rstrip(".") == norm for e in entries):
            return {"written": False, "reason": "duplicate", "entry": entry}

        entries.append(entry)
        evicted = 0
        # newest-first eviction: drop oldest until under the cap
        while True:
            body = header + "\n".join(f"- {e}" for e in entries) + "\n"
            if len(body) <= cap or len(entries) <= 1:
                break
            entries.pop(0)
            evicted += 1
        path.write_text(body)
        return {"written": True, "entry": entry, "entries": len(entries),
                "evicted": evicted, "bytes": len(body)}

    def remember(self, fact: str) -> Dict[str, Any]:
        """Add a durable fact to MEMORY.md."""
        return self._append(self.memory_path, MEMORY_HEADER, MEMORY_CAP, fact)

    def remember_user(self, fact: str) -> Dict[str, Any]:
        """Add a fact about the user to USER.md."""
        return self._append(self.user_path, USER_HEADER, USER_CAP, fact)

    def forget(self, needle: str) -> Dict[str, Any]:
        """Remove matching entries from both files."""
        removed = 0
        for path, header in ((self.memory_path, MEMORY_HEADER), (self.user_path, USER_HEADER)):
            entries = self._entries(path)
            keep = [e for e in entries if needle.lower() not in e.lower()]
            removed += len(entries) - len(keep)
            path.write_text(header + "\n".join(f"- {e}" for e in keep) + ("\n" if keep else ""))
        return {"removed": removed}

    # ── the point of all this ──
    def context_block(self) -> str:
        """
        The guaranteed-context string injected into every turn.
        Empty when nothing has been learned yet, so it costs nothing on a fresh install.
        """
        mem, usr = self.memory_entries(), self.user_entries()
        if not mem and not usr:
            return ""
        parts = []
        if usr:
            parts.append("About the user:\n" + "\n".join(f"- {e}" for e in usr))
        if mem:
            parts.append("Durable facts:\n" + "\n".join(f"- {e}" for e in mem))
        return "\n\n".join(parts)

    def stats(self) -> Dict[str, Any]:
        mem, usr = self.memory_entries(), self.user_entries()
        return {
            "memory_entries": len(mem),
            "user_entries": len(usr),
            "memory_bytes": len(self.read_memory()),
            "user_bytes": len(self.read_user()),
            "memory_cap": MEMORY_CAP,
            "user_cap": USER_CAP,
            "memory_path": str(self.memory_path),
            "user_path": str(self.user_path),
        }


# ── autonomous capture ──────────────────────────────────────────────────────
# Hermes "nudges itself" to persist knowledge. These patterns are the deterministic
# floor of that behaviour: they work with no LLM configured. When a model IS wired,
# swarm.py additionally asks it what was worth remembering.

USER_PATTERNS = [
    # Stop at a clause boundary: "my name is Ravi and I work at Acme" must capture
    # "Ravi", not the rest of the sentence. Additional capitalised words are treated
    # as surname ("Ada Lovelace"), but lowercase connectives end the match.
    (re.compile(r"\bmy name is ([A-Za-z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*)"), "Name: {}"),
    (re.compile(r"\bi am (?:a|an) ([\w .'-]{2,50}?)(?:\.|,|$)", re.I), "Role: {}"),
    (re.compile(r"\bi work (?:at|for) ([\w .'&-]{2,50}?)(?:\.|,|$)", re.I), "Works at: {}"),
    (re.compile(r"\bi(?:'m| am) (?:based )?in ([\w .'-]{2,40}?)(?:\.|,|$)", re.I), "Location: {}"),
    (re.compile(r"\bi prefer ([\w .,'\-/]{3,80}?)(?:\.|$)", re.I), "Prefers: {}"),
    (re.compile(r"\bcall me ([A-Za-z][\w .'-]{1,30})", re.I), "Prefers to be called: {}"),
]

MEMORY_PATTERNS = [
    (re.compile(r"\b(?:remember|note) that ([^.!?]{4,160})", re.I), "{}"),
    (re.compile(r"\bwe (?:use|are using) ([\w .,'\-/+]{3,80}?)(?:\.|$)", re.I), "Uses: {}"),
    (re.compile(r"\bthe (?:project|repo|codebase) (?:is|uses) ([^.!?]{3,120})", re.I),
     "Project: {}"),
    (re.compile(r"\balways ([^.!?]{4,120})", re.I), "Convention: always {}"),
    (re.compile(r"\bnever ([^.!?]{4,120})", re.I), "Convention: never {}"),
]


def extract_profile_facts(message: str) -> Dict[str, List[str]]:
    """Deterministic fact extraction — the no-LLM floor for self-nudging memory."""
    user_facts, mem_facts = [], []
    if not message or len(message) > 4000:
        return {"user": [], "memory": []}
    for rx, tmpl in USER_PATTERNS:
        m = rx.search(message)
        if m:
            val = " ".join(m.group(1).split()).strip(" .,")
            if 1 < len(val) <= 60:
                user_facts.append(tmpl.format(val))
    for rx, tmpl in MEMORY_PATTERNS:
        m = rx.search(message)
        if m:
            val = " ".join(m.group(1).split()).strip(" .,")
            if 3 < len(val) <= 160:
                mem_facts.append(tmpl.format(val))
    return {"user": user_facts[:2], "memory": mem_facts[:2]}
