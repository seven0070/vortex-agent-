"""Configuration management for the Vortex desktop client."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
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
        known_fields = {f.name for f in fields(DesktopConfig)}
        filtered = {key: value for key, value in defaults.items() if key in known_fields}
        base = DesktopConfig()
        filtered["backend_port"] = self._coerce_int(filtered.get("backend_port"), base.backend_port)
        filtered["poll_interval_ms"] = self._coerce_int(filtered.get("poll_interval_ms"), base.poll_interval_ms)
        filtered["auto_start_backend"] = self._coerce_bool(filtered.get("auto_start_backend"), base.auto_start_backend)
        filtered["connect_remote"] = self._coerce_bool(filtered.get("connect_remote"), base.connect_remote)
        try:
            return DesktopConfig(**filtered)
        except (TypeError, ValueError):
            return DesktopConfig()

    def save(self, config: DesktopConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")

    @staticmethod
    def _coerce_int(value, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_bool(value, fallback: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "on"):
                return True
            if normalized in ("false", "0", "no", "off"):
                return False
            return fallback
        return fallback
