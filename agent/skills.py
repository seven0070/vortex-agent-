"""Skills hub — agentskills.io-compatible SKILL.md playbooks + learned skills."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from vortex_constants import BUNDLED_SKILLS, SKILLS_DIR, ensure_home


def _parse_skill_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta: Dict[str, str] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            front, body = parts[1], parts[2]
            for line in front.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip().strip("\"'")
    name = meta.get("name") or path.parent.name if path.name == "SKILL.md" else path.stem
    return {
        "name": name,
        "description": meta.get("description") or body.strip().splitlines()[0][:160] if body.strip() else "",
        "body": body.strip(),
        "path": str(path),
        "source": meta.get("source", "bundled" if "skills" in str(path) else "user"),
        "tags": [t.strip() for t in (meta.get("tags") or "").split(",") if t.strip()],
    }


class SkillHub:
    """Discover, load, and save skills (procedural memory)."""

    def __init__(self):
        ensure_home()
        self.user_dir = SKILLS_DIR
        self.bundled = BUNDLED_SKILLS
        self._sync_bundled()

    def _sync_bundled(self):
        """Copy bundled skills into user dir if missing (non-destructive)."""
        if not self.bundled.exists():
            return
        for src in self.bundled.rglob("SKILL.md"):
            rel = src.relative_to(self.bundled)
            dst = self.user_dir / rel
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    def list(self) -> List[dict]:
        out = []
        seen = set()
        for base in (self.user_dir, self.bundled):
            if not base.exists():
                continue
            for p in sorted(base.rglob("SKILL.md")):
                try:
                    skill = _parse_skill_md(p)
                except Exception:
                    continue
                if skill["name"] in seen:
                    continue
                seen.add(skill["name"])
                out.append(
                    {
                        "name": skill["name"],
                        "description": skill["description"],
                        "source": skill["source"],
                        "tags": skill["tags"],
                    }
                )
            # also JSON learned skills
            for p in sorted(base.glob("*.json")):
                try:
                    data = json.loads(p.read_text())
                    name = data.get("name") or p.stem
                    if name in seen:
                        continue
                    seen.add(name)
                    out.append(
                        {
                            "name": name,
                            "description": data.get("description", ""),
                            "source": "learned",
                            "tags": data.get("steps", [])[:5],
                        }
                    )
                except Exception:
                    continue
        return out

    def get(self, name: str) -> Optional[dict]:
        # SKILL.md first
        for base in (self.user_dir, self.bundled):
            if not base.exists():
                continue
            for p in base.rglob("SKILL.md"):
                skill = _parse_skill_md(p)
                if skill["name"] == name or p.parent.name == name:
                    return skill
            jp = base / f"{name}.json"
            if jp.exists():
                data = json.loads(jp.read_text())
                return {
                    "name": data.get("name", name),
                    "description": data.get("description", ""),
                    "body": json.dumps(data, indent=2),
                    "source": "learned",
                }
        return None

    def save_learned(self, name: str, description: str, steps: list):
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "skill"
        path = self.user_dir / f"{slug}.json"
        path.write_text(
            json.dumps(
                {
                    "name": slug,
                    "description": description,
                    "steps": steps,
                    "created": datetime.now().isoformat(timespec="seconds"),
                    "source": "learned",
                },
                indent=2,
            )
        )
        return slug

    def prompt_block(self, limit: int = 12) -> str:
        items = self.list()[:limit]
        if not items:
            return ""
        lines = ["## Available skills (use skill_view to load full instructions)"]
        for s in items:
            lines.append(f"- **{s['name']}**: {s['description'][:100]}")
        return "\n".join(lines)
