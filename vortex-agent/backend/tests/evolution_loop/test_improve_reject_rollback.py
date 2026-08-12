"""
Prove the three evolution cases:

  v001 → improve → v002 active
  v003 regression → REJECT → v002 remains active
  post-deploy degrade → ROLLBACK → stable restored
"""
import os
import tempfile
import unittest

os.environ["VORTEX_HOME"] = tempfile.mkdtemp(prefix="vortex-1-evo-")

from evolution.compiler import compile_math, default_overlay, set_overlay  # noqa: E402
from evolution.overlay import Overlay, activate, load_pointers, save_pointers, default_pointers  # noqa: E402
from evolution.workspace import prune_tmp_worktrees  # noqa: E402
from memory import Memory  # noqa: E402
from swarm import VortexAgent  # noqa: E402


class ImproveRejectRollbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        set_overlay(default_overlay())
        activate(Overlay.genesis())
        save_pointers(default_pointers())
        cls.memory = Memory()
        cls.agent = VortexAgent(cls.memory)
        cls.evo = cls.agent.rsi.evolution

    @classmethod
    def tearDownClass(cls):
        prune_tmp_worktrees()

    def test_improve_then_reject_regression_then_rollback(self):
        set_overlay(default_overlay())
        activate(Overlay.genesis())
        save_pointers(default_pointers())
        self.assertNotIn("+ 5", compile_math("what is 15 times 3 plus 5") or "")

        # 1. Improve: v001 → candidate that actually patches → promote
        improved = self.evo.evolve_once()
        self.assertEqual(improved.get("decision"), "promoted", improved)
        self.assertIn("50", self.agent.chat("what is 15 times 3 plus 5"))
        ptr = load_pointers()
        stable = ptr["current"]
        self.assertIsNotNone(stable)

        # 2. Known regression: disable compiler gains → REJECT, stable stays active
        worse = Overlay(improved.get("overlay") or default_overlay())
        regression = self.evo.candidate_gen.create_candidate(
            worse.generation_id,
            {"hypothesis": "known regression", "change_set": [{"type": "regression_disable"}]},
            [{"type": "regression_disable", "file": "evolution/compiler.py"}],
            parent_overlay=worse,
        )
        reviewed = self.evo.review_candidate(regression)
        self.assertEqual(reviewed.get("decision"), "rejected", reviewed)
        self.assertLess(
            float((reviewed.get("benchmark_results") or {}).get("score") or 0),
            float((reviewed.get("baseline") or {}).get("score") or 1),
        )
        ptr_after = load_pointers()
        self.assertEqual(ptr_after["current"], stable)
        self.assertEqual(compile_math("what is 15 times 3 plus 5"), "print(15 * 3 + 5)")

        # 3. Post-deploy degradation → automatic rollback
        ptr = load_pointers()
        ptr["stable_live_score"] = 0.99
        save_pointers(ptr)
        for i in range(6):
            self.memory.save_trace({
                "generation": self.memory.current_generation(),
                "task": f"post-deploy fail {i}",
                "bot": "chief",
                "status": "error",
                "score": 0.05,
                "latency_ms": 1,
            })
        rb = self.evo.rollback.monitor_and_maybe_rollback(window=6, floor=0.4)
        self.assertEqual(rb.get("action"), "rollback", rb)


if __name__ == "__main__":
    unittest.main()
