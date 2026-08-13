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

    def is_running(self) -> bool:
        try:
            response = requests.get(f"{self.config.local_backend_url}/health", timeout=1)
            return response.ok
        except requests.RequestException:
            return False

    def start_if_needed(self, timeout_seconds: int = 15) -> bool:
        if self.config.connect_remote or not self.config.auto_start_backend:
            return self.is_running() if not self.config.connect_remote else True
        if self.is_running():
            return True

        if not self.backend_main_path.exists():
            return False

        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform.startswith("win") else 0
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
            assert self.process and self.process.stdout
            for line in self.process.stdout:
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
