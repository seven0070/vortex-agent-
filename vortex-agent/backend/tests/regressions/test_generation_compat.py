"""Permanent regression: later generations must not clobber last-known-good."""
import os
import tempfile
import unittest

os.environ["VORTEX_HOME"] = tempfile.mkdtemp(prefix="vortex-reg-")

from evolution.overlay import Overlay, load_pointers  # noqa: E402
from evolution.patcher import CandidatePatcher  # noqa: E402
from pathlib import Path  # noqa: E402


class GenerationCompatTests(unittest.TestCase):
    def test_parent_release_survives_child(self):
        patcher = CandidatePatcher()
        a = patcher.create_candidate(0, {"hypothesis": "a", "change_set": [{"type": "compiler_improve"}]},
                                     [{"type": "compiler_improve"}], parent_overlay=Overlay.genesis())
        parent = Path(a["release_dir"])
        marker = parent / "KEEP_ME"
        marker.write_text("stable")
        b = patcher.create_candidate(a["generation_id"], {"hypothesis": "b", "change_set": [{"type": "router_boost"}]},
                                     [{"type": "router_boost"}], parent_overlay=Overlay(a["overlay"]))
        self.assertTrue(marker.exists())
        self.assertEqual(marker.read_text(), "stable")
        self.assertNotEqual(a["release_dir"], b["release_dir"])
        self.assertTrue(Path(b["release_dir"]).exists())

    def test_pointers_default_safe(self):
        ptr = load_pointers()
        self.assertIn("current", ptr)
        self.assertIn("last_known_good", ptr)
        self.assertIn("canary", ptr)


if __name__ == "__main__":
    unittest.main()
