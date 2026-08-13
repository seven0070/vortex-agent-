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

    @staticmethod
    def _read(path):
        """
        Read one skill file, tolerating corruption.

        A skill file can be truncated by an interrupted write or a crash mid-save.
        Previously a single bad file raised JSONDecodeError out of list(), which
        broke /skills, GET /api/skills and autonomous skill capture — one unreadable
        file took out the whole library. A corrupt skill is skipped, not fatal.
        """
        try:
            data = json.loads(path.read_text() or "null")
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def list(self):
        out = []
        for f in sorted(self.dir.glob("*.json")):
            data = self._read(f)
            if data is not None:
                out.append(data)
        return out

    def get(self, name):
        p = self.dir / f"{name}.json"
        return self._read(p) if p.exists() else None


class BugLibrary:
    """Global bug patterns — one bot's lesson becomes every bot's lesson."""
    def __init__(self):
        self.path = vortex_home() / "bug_patterns.json"
        # Same failure mode as the skill library: a truncated bug_patterns.json used
        # to raise out of the constructor, and BugLibrary is built during agent
        # startup — so one corrupt file made the whole agent unstartable.
        self.patterns = []
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text() or "[]")
                if isinstance(loaded, list):
                    self.patterns = loaded
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                self.patterns = []

    def add(self, pattern):
        self.patterns.append({**pattern, "seen": datetime.now().isoformat()})
        self.path.write_text(json.dumps(self.patterns, indent=2))

    def match(self, error_text):
        low = error_text.lower()
        for p in self.patterns:
            if any(s.lower() in low for s in p.get("symptoms", [])):
                return p
        return None
