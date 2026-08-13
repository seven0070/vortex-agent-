import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from api_client import VortexApiClient
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


if __name__ == "__main__":
    unittest.main()
