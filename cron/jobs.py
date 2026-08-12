"""Minimal cron job store (Hermes cron counterpart — extension point)."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from vortex_constants import CRON_DIR, ensure_home


@dataclass
class CronJob:
    id: str
    name: str
    goal: str
    schedule: str = "manual"  # free-form for now; runner decides
    enabled: bool = True
    last_run: str = ""
    last_status: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)


class CronStore:
    def __init__(self, path: Optional[Path] = None):
        ensure_home()
        self.path = path or (CRON_DIR / "jobs.json")
        self.jobs: Dict[str, CronJob] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                for row in data.get("jobs", []):
                    j = CronJob(**{k: row[k] for k in CronJob.__dataclass_fields__ if k in row})
                    self.jobs[j.id] = j
            except Exception:
                self.jobs = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"jobs": [j.to_dict() for j in self.jobs.values()]}, indent=2)
        )

    def list(self) -> List[dict]:
        return [j.to_dict() for j in self.jobs.values()]

    def add(self, name: str, goal: str, schedule: str = "manual") -> dict:
        jid = uuid.uuid4().hex[:10]
        job = CronJob(id=jid, name=name, goal=goal, schedule=schedule)
        self.jobs[jid] = job
        self._save()
        return job.to_dict()

    def remove(self, jid: str) -> bool:
        if jid in self.jobs:
            del self.jobs[jid]
            self._save()
            return True
        return False

    def mark(self, jid: str, status: str):
        if jid in self.jobs:
            self.jobs[jid].last_run = datetime.now().isoformat(timespec="seconds")
            self.jobs[jid].last_status = status
            self._save()
