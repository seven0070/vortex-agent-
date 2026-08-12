"""Permanent Vortex 1.0 benchmark: V(n+1) > V(n) is earned, not assumed."""
import os
import tempfile
import unittest

os.environ["VORTEX_HOME"] = tempfile.mkdtemp(prefix="vortex-1-bench-")

from evals import VortexBenchmark, run_suite, CATEGORIES  # noqa: E402
from evolution.compiler import default_overlay  # noqa: E402
from evolution.harness import run_suite as overlay_suite  # noqa: E402
from evolution.promotion import PromotionPolicy  # noqa: E402
from memory import Memory  # noqa: E402
from pathlib import Path  # noqa: E402
from swarm import VortexAgent  # noqa: E402


PERMANENT = {
    "reasoning", "planning", "memory_recall", "tool_selection", "coding",
    "multi_agent", "reliability", "safety", "regression",
}


class PermanentBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = VortexAgent(Memory())

    def test_categories_cover_the_contract(self):
        self.assertTrue(PERMANENT.issubset(set(CATEGORIES) | {"safety"}))

    def test_live_suite_holds_baseline(self):
        suite = run_suite(self.agent, persist=False)
        self.assertGreaterEqual(suite["score"], 0.6)
        self.assertGreaterEqual(suite["passed"], 5)

    def test_vn1_must_beat_vn(self):
        fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "golden_tasks.json"
        import json
        data = json.loads(fixtures.read_text())
        base = overlay_suite(default_overlay(), data, include_capability=True)
        better = default_overlay()
        better["compiler"]["chained_arithmetic"] = True
        better["compiler"]["power_operator"] = True
        cand = overlay_suite(better, data, include_capability=True)
        self.assertGreater(cand["score"], base["score"])
        policy = PromotionPolicy().decide(
            baseline=base, candidate=cand,
            security={"passed": True, "risk_score": 0.1},
            tests={"passed": True}, canary={"passed": True},
        )
        self.assertEqual(policy["decision"], "promote")
        equal = PromotionPolicy().decide(
            baseline=cand, candidate=dict(cand),
            security={"passed": True, "risk_score": 0.1},
            tests={"passed": True}, canary={"passed": True},
        )
        self.assertEqual(equal["decision"], "reject")
        self.assertFalse(equal["gates"]["benchmark_gt_stable"])

    def test_comprehensive_runner(self):
        vb = VortexBenchmark(self.agent)
        comp = vb.run_comprehensive(persist=False)
        self.assertGreaterEqual(comp["score"], 0.5)
        self.assertIn("breakdown", comp)


if __name__ == "__main__":
    unittest.main()
