"""Security and governance gates — no production overwrite, deny dangerous ops."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ["VORTEX_HOME"] = tempfile.mkdtemp(prefix="vortex-1-sec-")

from evolution.overlay import Overlay  # noqa: E402
from evolution.patcher import CandidatePatcher  # noqa: E402
from evolution.security import SecurityScanner  # noqa: E402
from memory import Memory  # noqa: E402
from swarm import VortexAgent  # noqa: E402


class SecurityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = VortexAgent(Memory())

    def test_governance_denies_rm(self):
        dec = self.agent.governance.evaluate(task="rm -rf /", context={}, agent="chief", action="execute")
        self.assertEqual(dec["action"], "DENY")

    def test_promote_without_gates_denied(self):
        dec = self.agent.governance.authorize_evolution(
            "promote",
            candidate={"generation_id": 1, "production_write": False},
            gates={"all_passed": False},
        )
        self.assertEqual(dec["action"], "DENY")

    def test_production_write_denied(self):
        dec = self.agent.governance.authorize_evolution(
            "overwrite_production", candidate={"production_write": True},
        )
        self.assertEqual(dec["action"], "DENY")
        scan = SecurityScanner().scan({"production_write": True, "change_set": [], "checkout_dir": ""})
        self.assertFalse(scan["passed"])

    def test_candidate_does_not_touch_live_compiler(self):
        prod = Path(__file__).resolve().parents[2] / "evolution" / "compiler.py"
        before = prod.read_text()
        CandidatePatcher().create_candidate(
            0,
            {"hypothesis": "x", "change_set": [{"type": "compiler_improve"}]},
            [{"type": "compiler_improve"}],
            parent_overlay=Overlay.genesis(),
        )
        self.assertEqual(prod.read_text(), before)
        self.assertIn('"chained_arithmetic": False', before)


if __name__ == "__main__":
    unittest.main()
