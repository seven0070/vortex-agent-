import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from api_client import VortexApiClient
from backend_manager import BackendManager
from config import ConfigManager, DesktopConfig


class DesktopConfigTests(unittest.TestCase):
    def test_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "desktop.json"
            mgr = ConfigManager(path)
            cfg = DesktopConfig(backend_url="https://example.com", connect_remote=True, poll_interval_ms=5000)
            mgr.save(cfg)
            loaded = mgr.load()
            self.assertEqual(loaded.backend_url, "https://example.com")
            self.assertTrue(loaded.connect_remote)
            self.assertEqual(loaded.poll_interval_ms, 5000)

    def test_config_load_ignores_unknown_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "desktop.json"
            path.write_text(json.dumps({"backend_url": "https://example.com", "unknown_field": "x"}), encoding="utf-8")
            mgr = ConfigManager(path)
            loaded = mgr.load()
            self.assertEqual(loaded.backend_url, "https://example.com")
            self.assertFalse(hasattr(loaded, "unknown_field"))

    def test_config_load_invalid_types_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "desktop.json"
            path.write_text(json.dumps({"backend_port": "bad", "poll_interval_ms": "bad", "connect_remote": "no"}), encoding="utf-8")
            mgr = ConfigManager(path)
            loaded = mgr.load()
            self.assertEqual(loaded.backend_port, DesktopConfig.backend_port)
            self.assertEqual(loaded.poll_interval_ms, DesktopConfig.poll_interval_ms)
            self.assertFalse(loaded.connect_remote)


class ApiClientTests(unittest.TestCase):
    @patch("api_client.requests.Session.request")
    def test_health_request_uses_expected_url(self, request_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"status": "healthy"}
        request_mock.return_value = response

        client = VortexApiClient("http://127.0.0.1:8765")
        health = client.health()

        self.assertEqual(health["status"], "healthy")
        request_mock.assert_called_once()
        args, kwargs = request_mock.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "http://127.0.0.1:8765/health")
        self.assertIn("timeout", kwargs)


class BackendManagerTests(unittest.TestCase):
    @patch("backend_manager.requests.get")
    def test_remote_mode_validates_remote_health(self, get_mock):
        response = Mock()
        response.ok = True
        get_mock.return_value = response

        cfg = DesktopConfig(backend_url="https://remote.example", connect_remote=True, auto_start_backend=False)
        manager = BackendManager(cfg)
        self.assertTrue(manager.start_if_needed())
        get_mock.assert_called_once_with("https://remote.example/health", timeout=1)


if __name__ == "__main__":
    unittest.main()
