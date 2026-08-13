"""Local backend lifecycle management for desktop app."""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

import requests

from config import DesktopConfig


class BackendManager:
    def __init__(self, config: DesktopConfig):
        self.config = config
        self.process: subprocess.Popen | None = None
        self._logs = deque(maxlen=2000)
        self._reader_thread: threading.Thread | None = None

    @property
    def backend_main_path(self) -> Path:
        return Path(__file__).resolve().parents[1] / "backend" / "main.py"

    def _is_url_running(self, base_url: str) -> bool:
        health_url = f"{base_url.rstrip('/')}/health"
        try:
            response = requests.get(health_url, timeout=1)
            return response.ok
        except requests.RequestException:
            return False

    def is_running(self) -> bool:
        return self._is_url_running(self.config.local_backend_url)

    def start_if_needed(self, timeout_seconds: int = 15) -> bool:
        if self.config.connect_remote:
            return self._is_url_running(self.config.backend_url)
        if not self.config.auto_start_backend:
            return self.is_running()
        if self.is_running():
            return True

        if not self.backend_main_path.exists():
            return False

        creation_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags = creation_group if sys.platform.startswith("win") else 0
        self.process = subprocess.Popen(
            [sys.executable, str(self.backend_main_path), str(self.config.backend_port)],
            cwd=str(self.backend_main_path.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )
        self._start_log_reader()

        end = time.time() + timeout_seconds
        while time.time() < end:
            if self.is_running():
                return True
            if self.process.poll() is not None:
                return False
            time.sleep(0.5)
        return False

    def _start_log_reader(self) -> None:
        if not self.process or not self.process.stdout:
            return

        def read_stream() -> None:
            process = self.process
            if not process or not process.stdout:
                return
            for line in process.stdout:
                self._logs.append(line.rstrip())

        self._reader_thread = threading.Thread(target=read_stream, daemon=True)
        self._reader_thread.start()

    def get_logs(self, text_filter: str = "") -> list[str]:
        logs = list(self._logs)
        if not text_filter:
            return logs
        needle = text_filter.lower()
        return [line for line in logs if needle in line.lower()]

    def stop(self) -> None:
        if not self.process:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
