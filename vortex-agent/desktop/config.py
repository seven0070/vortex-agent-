"""Configuration management for the Vortex desktop client."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class DesktopConfig:
    backend_url: str = "http://127.0.0.1:8765"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8765
    auto_start_backend: bool = True
    connect_remote: bool = False
    poll_interval_ms: int = 3000

    @property
    def local_backend_url(self) -> str:
        return f"http://{self.backend_host}:{self.backend_port}"

    @property
    def active_backend_url(self) -> str:
        return self.backend_url if self.connect_remote else self.local_backend_url


class ConfigManager:
    def __init__(self, path: Path | None = None):
        self.path = path or (Path.home() / ".vortex_agent_desktop.json")

    def load(self) -> DesktopConfig:
        if not self.path.exists():
            cfg = DesktopConfig()
            self.save(cfg)
            return cfg

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return DesktopConfig()

        defaults = asdict(DesktopConfig())
        defaults.update(data or {})
        return DesktopConfig(**defaults)

    def save(self, config: DesktopConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
