"""Shared skill library + global bug-pattern library."""
import json
from datetime import datetime

from paths import vortex_home


class SkillLibrary:
    """Skills saved by any bot are visible to all bots."""
    def __init__(self):
        self.dir = vortex_home() / "skills"
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, name, description, steps, shared=True):
        (self.dir / f"{name}.json").write_text(json.dumps({
            "name": name, "description": description, "steps": steps,
            "shared": shared, "created": datetime.now().isoformat(),
        }, indent=2))

    def list(self):
        out = []
        for f in sorted(self.dir.glob("*.json")):
            out.append(json.loads(f.read_text()))
        return out

    def get(self, name):
        p = self.dir / f"{name}.json"
        return json.loads(p.read_text()) if p.exists() else None


class BugLibrary:
    """Global bug patterns — one bot's lesson becomes every bot's lesson."""
    def __init__(self):
        self.path = vortex_home() / "bug_patterns.json"
        self.patterns = json.loads(self.path.read_text()) if self.path.exists() else []

    def add(self, pattern):
        self.patterns.append({**pattern, "seen": datetime.now().isoformat()})
        self.path.write_text(json.dumps(self.patterns, indent=2))

    def match(self, error_text):
        low = error_text.lower()
        for p in self.patterns:
            if any(s.lower() in low for s in p.get("symptoms", [])):
                return p
        return None
