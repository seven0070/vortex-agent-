"""Evolution Engine v1 — real patches, sandbox, canary, rollback, promotion policy."""
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ["VORTEX_HOME"] = tempfile.mkdtemp(prefix="vortex-evo-")

from evolution.compiler import compile_math, set_overlay, default_overlay  # noqa: E402
from evolution.overlay import Overlay, activate, load_pointers, release_path  # noqa: E402
from evolution.patcher import CandidatePatcher  # noqa: E402
from evolution.sandbox import SandboxRunner  # noqa: E402
from evolution.security import SecurityScanner  # noqa: E402
from evolution.promotion import PromotionPolicy  # noqa: E402
from memory import Memory  # noqa: E402
from swarm import VortexAgent  # noqa: E402
from self_improve import compile_math as rsi_compile_math  # noqa: E402


class CompilerOverlayTests(unittest.TestCase):
    def tearDown(self):
        set_overlay(None)
        activate(Overlay.genesis())

    def test_baseline_does_not_compile_chained(self):
        set_overlay(default_overlay())
        code = compile_math("what is 15 times 3 plus 5")
        self.assertIsNotNone(code)
        self.assertNotIn("15 * 3 + 5", code)
        self.assertIn("15 * 3", code)

    def test_chained_overlay_compiles_and_equals_50(self):
        ov = default_overlay()
        ov["compiler"]["chained_arithmetic"] = True
        set_overlay(ov)
        code = compile_math("what is 15 times 3 plus 5")
        self.assertEqual(code, "print(15 * 3 + 5)")
        self.assertEqual(eval(code[len("print("):-1]), 50)

    def test_existing_two_operand_still_works(self):
        set_overlay(default_overlay())
        self.assertEqual(compile_math("what is 12 times 8"), "print(12 * 8)")
        self.assertEqual(rsi_compile_math("sum of 40 and 2"), "print(40 + 2)")


class RealPatchAndSandboxTests(unittest.TestCase):
    def test_patcher_writes_real_checkout_not_metadata_only(self):
        patcher = CandidatePatcher()
        cand = patcher.create_candidate(
            0,
            {"hypothesis": "enable chained arithmetic", "change_set": [
                {"file": "overlay.json", "type": "compiler_improve", "target": "reasoning-chain"}
            ]},
            [{"file": "overlay.json", "type": "compiler_improve", "target": "reasoning-chain"}],
            parent_overlay=Overlay.genesis(),
        )
        checkout = Path(cand["checkout_dir"])
        self.assertTrue((checkout / "overlay.json").exists())
        self.assertTrue((checkout / "compiler.py").exists())
        self.assertTrue((checkout / "harness.py").exists())
        self.assertTrue((checkout / "fixtures.json").exists())
        overlay = json.loads((checkout / "overlay.json").read_text())
        self.assertTrue(overlay["compiler"]["chained_arithmetic"])
        self.assertTrue(cand["applied_patches"])
        self.assertFalse(cand["production_write"])
        diff = Path(cand["release_dir"]) / "patches" / "applied.diff"
        self.assertTrue(diff.exists())
        self.assertIn("chained_arithmetic", diff.read_text())

    def test_sandbox_is_real_subprocess_not_mock(self):
        patcher = CandidatePatcher()
        cand = patcher.create_candidate(
            0,
            {"hypothesis": "chained", "change_set": [{"type": "compiler_improve", "target": "reasoning-chain"}]},
            [{"type": "compiler_improve", "target": "reasoning-chain"}],
            parent_overlay=Overlay.genesis(),
        )
        res = SandboxRunner(timeout=20).run_tests(cand)
        self.assertTrue(res["passed"])
        detail = res["result"]["detail"]
        self.assertFalse(res["result"].get("mock"))
        self.assertNotIn("sandbox tests passed (mock)", res["result"].get("output", ""))
        self.assertTrue(detail.get("syntax_ok"))
        names = {c["name"]: c["ok"] for c in detail.get("cases", [])}
        self.assertTrue(names.get("nl-math-multiply"))
        self.assertTrue(names.get("reasoning-chain"))

    def test_sandbox_rejects_missing_checkout(self):
        res = SandboxRunner().run_tests({"checkout_dir": "/tmp/does-not-exist-vortex", "change_set": []})
        self.assertFalse(res["passed"])
        self.assertIn("missing harness", res["result"]["output"])


class PromotionPolicyTests(unittest.TestCase):
    def test_equal_score_alone_is_not_enough(self):
        policy = PromotionPolicy()
        baseline = {"quality": 0.7, "score": 0.7, "reliability": 0.7, "latency_ms": 10, "cost": 4, "regressions": [], "critical_regressions": []}
        candidate = dict(baseline)
        out = policy.decide(
            baseline, candidate,
            security={"passed": True, "risk_score": 0.1},
            tests={"passed": True},
            canary={"passed": True},
        )
        self.assertEqual(out["decision"], "reject")
        self.assertFalse(out["gates"]["improvement_earned"])

    def test_quality_up_with_all_gates_promotes(self):
        policy = PromotionPolicy()
        baseline = {"quality": 0.5, "score": 0.5, "reliability": 0.5, "latency_ms": 20, "cost": 7, "regressions": [], "critical_regressions": []}
        candidate = {"quality": 0.8, "score": 0.8, "reliability": 0.7, "latency_ms": 18, "cost": 7, "regressions": [], "critical_regressions": []}
        out = policy.decide(baseline, candidate, security={"passed": True, "risk_score": 0.1},
                            tests={"passed": True}, canary={"passed": True})
        self.assertEqual(out["decision"], "promote")
        self.assertTrue(out["all_passed"])

    def test_regression_blocks_promotion(self):
        policy = PromotionPolicy()
        baseline = {"quality": 0.5, "score": 0.5, "reliability": 0.5, "latency_ms": 10, "cost": 4, "regressions": [], "critical_regressions": []}
        candidate = {"quality": 0.9, "score": 0.9, "reliability": 0.9, "latency_ms": 10, "cost": 4,
                     "regressions": ["nl-math-multiply"], "critical_regressions": ["nl-math-multiply"]}
        out = policy.decide(baseline, candidate, security={"passed": True, "risk_score": 0.1},
                            tests={"passed": True}, canary={"passed": True})
        self.assertEqual(out["decision"], "reject")


class EndToEndEvolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["VORTEX_HOME"] = tempfile.mkdtemp(prefix="vortex-evo-e2e-")
        set_overlay(None)
        activate(Overlay.genesis())
        cls.memory = Memory()
        cls.agent = VortexAgent(cls.memory)

    def test_full_loop_promotes_real_compiler_improvement(self):
        set_overlay(default_overlay())
        activate(Overlay.genesis())
        from evolution.overlay import save_pointers, default_pointers
        save_pointers(default_pointers())
        before = compile_math("what is 15 times 3 plus 5")
        self.assertNotIn("+ 5", before or "")

        rec = self.agent.rsi.evolution.evolve_once()
        self.assertEqual(rec.get("decision"), "promoted", rec)
        self.assertEqual(rec.get("status"), "deployed")
        self.assertTrue(rec.get("applied_patches"))
        self.assertFalse((rec.get("sandbox_result") or {}).get("mock", True))
        self.assertFalse((rec.get("canary_results") or {}).get("mock", True))
        self.assertIn("chained_arithmetic", " ".join(rec.get("applied_patches") or []))

        after = compile_math("what is 15 times 3 plus 5")
        self.assertEqual(after, "print(15 * 3 + 5)")

        reply = self.agent.chat("what is 15 times 3 plus 5")
        self.assertIn("50", reply)

        gen = rec["generation_id"]
        release = release_path(gen)
        self.assertTrue((release / "overlay.json").exists())
        self.assertTrue((release / "evolution_record.json").exists())
        self.assertTrue((release / "checkout" / "compiler.py").exists())

        ptr = load_pointers()
        self.assertEqual(ptr["current"], f"v{gen:03d}")
        self.assertEqual(ptr["last_known_good"], f"v{gen:03d}")

    def test_lkg_not_overwritten_on_later_generation(self):
        evo = self.agent.rsi.evolution
        first = evo.evolve_once()
        first_dir = Path(first["release_dir"])
        snapshot = (first_dir / "overlay.json").read_text()
        second = evo.evolve_once()
        self.assertTrue(first_dir.exists())
        self.assertEqual((first_dir / "overlay.json").read_text(), snapshot)
        self.assertNotEqual(first["generation_id"], second["generation_id"])
        self.assertTrue(Path(second["release_dir"]).exists())

    def test_rollback_restores_previous_overlay(self):
        evo = self.agent.rsi.evolution
        rec = evo.evolve_once()
        current = rec["generation_id"]
        # roll back to genesis (no prior LKG if this is first) — still a real restore
        rb = evo.rollback.rollback("test rollback", failed_generation=current)
        self.assertEqual(rb["action"], "rollback")
        live = compile_math("what is 15 times 3 plus 5")
        # after rollback to LKG, either genesis (no chain) or previous promoted
        self.assertIsNotNone(live)

    def test_governance_denies_ungated_promote(self):
        gov = self.agent.governance
        dec = gov.authorize_evolution(
            "promote",
            candidate={"generation_id": 99, "production_write": False},
            gates={"all_passed": False, "reason": "quality not up"},
        )
        self.assertEqual(dec["action"], "DENY")
        dec2 = gov.authorize_evolution(
            "overwrite_production",
            candidate={"production_write": True},
        )
        self.assertEqual(dec2["action"], "DENY")

    def test_security_flags_production_write(self):
        scan = SecurityScanner().scan({"production_write": True, "change_set": [], "checkout_dir": ""})
        self.assertFalse(scan["passed"])

    def test_pipeline_layers_on_simple_request(self):
        self.agent.chat("what is 12 times 8")
        layers = (self.agent.last_pipeline or {}).get("layers") or []
        for required in ("interface", "sovereign", "governance", "orchestration",
                         "resolution", "memory", "evaluation", "self-improvement"):
            self.assertTrue(any(required in layer for layer in layers), f"missing {required} in {layers}")

    def test_memory_changes_the_answer(self):
        self.agent.memory.remember(
            "Project Orion deadline is 2026-12-01",
            kind="fact",
        )
        reply = self.agent.chat("what is the Project Orion deadline?")
        self.assertIn("2026-12-01", reply)
        self.assertTrue((self.agent.last_pipeline or {}).get("memory_hit"))


if __name__ == "__main__":
    unittest.main()
