"""
Tests for real self-modification.

The important tests here are the ones asserting the agent CANNOT do things:
edit its own tests, edit the frozen eval, write dangerous code, or apply an
unverified diff. A self-modifying agent is only as trustworthy as its refusals.

Note: tests that run the full sandbox pipeline are slower (they copy the tree and
run the suite in a subprocess). They are marked in their docstrings.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code_mutation import (BACKEND, ApprovalQueue, CodeEvolution, Diff,
                           DiffSecurityScanner, MutationProposer, SandboxedRepo,
                           _is_mutable)


class ImmutabilityTests(unittest.TestCase):
    """What the agent must never be able to edit."""

    def test_frozen_eval_is_protected(self):
        """If it can edit evals.py it can pass any gate by rewriting the gate."""
        ok, why = _is_mutable("evals.py")
        self.assertFalse(ok)
        self.assertIn("protected", why)

    def test_tests_are_protected(self):
        for p in ("tests/test_rsi.py", "tests/test_architecture.py", "tests/anything.py"):
            self.assertFalse(_is_mutable(p)[0], f"{p} must be immutable")

    def test_mutation_engine_cannot_self_exempt(self):
        self.assertFalse(_is_mutable("code_mutation.py")[0])

    def test_path_escape_blocked(self):
        for p in ("../README.md", "/etc/passwd", "../../setup.py", "a/../../x.py"):
            self.assertFalse(_is_mutable(p)[0], f"{p} must be blocked")

    def test_non_python_blocked(self):
        self.assertFalse(_is_mutable("static/index.html")[0])

    def test_nonexistent_blocked(self):
        self.assertFalse(_is_mutable("no_such_module.py")[0])

    def test_ordinary_module_is_mutable(self):
        self.assertTrue(_is_mutable("skill_manage.py")[0])
        self.assertTrue(_is_mutable("profile_memory.py")[0])


class SecurityScannerTests(unittest.TestCase):
    def setUp(self):
        self.s = DiffSecurityScanner()

    def _scan(self, added: str):
        return self.s.scan([Diff("skill_manage.py", "x = 1\n", added)])

    def test_blocks_dangerous_constructs(self):
        for bad in ('os.system("ls")\n', 'exec("x")\n', 'eval("1")\n',
                    'subprocess.run(["ls"])\n', 'shutil.rmtree("/")\n',
                    'open("/tmp/x","w")\n', '__import__("os")\n',
                    'pickle.loads(b"")\n'):
            self.assertFalse(self._scan(bad)["passed"], f"should block: {bad!r}")

    def test_blocks_restricted_imports(self):
        for bad in ("import os\n", "import socket\n", "from subprocess import run\n"):
            self.assertFalse(self._scan(bad)["passed"], f"should block: {bad!r}")

    def test_allows_benign_code(self):
        for good in ("import json\n", "from typing import List\n",
                     "COMPLEXITY_TOOL_CALLS = 3\n", "def f(x):\n    return x + 1\n"):
            self.assertTrue(self._scan(good)["passed"], f"should allow: {good!r}")

    def test_comments_are_not_flagged(self):
        self.assertTrue(self._scan("# we avoid os.system here\n")["passed"])

    def test_immutable_target_is_critical(self):
        r = self.s.scan([Diff("evals.py", "a\n", "b\n")])
        self.assertFalse(r["passed"])
        self.assertEqual(r["findings"][0]["severity"], "critical")


class DiffTests(unittest.TestCase):
    def test_unified_and_stats(self):
        d = Diff("x.py", "a = 1\nb = 2\n", "a = 1\nb = 3\n", "bump b")
        self.assertIn("-b = 2", d.unified)
        self.assertIn("+b = 3", d.unified)
        self.assertEqual(d.stats(), {"added": 1, "removed": 1})

    def test_added_lines_only(self):
        d = Diff("x.py", "old\n", "new\n")
        self.assertEqual(d.added_lines, ["new"])


class ProposerTests(unittest.TestCase):
    def test_retune_respects_bounds(self):
        p = MutationProposer()
        # MEMORY_CAP has an upper bound of 8000; ask to go up from the real value
        diffs = p._retune("profile_memory.py", "MEMORY_CAP", 500, 8000, "up")
        self.assertEqual(len(diffs), 1)
        self.assertIn("MEMORY_CAP", diffs[0].unified)

    def test_retune_clamped_at_bound_produces_nothing(self):
        p = MutationProposer()
        # a bound equal to the current value leaves no room to move
        import profile_memory
        cur = profile_memory.MEMORY_CAP
        self.assertEqual(p._retune("profile_memory.py", "MEMORY_CAP", cur, cur, "up"), [])

    def test_unknown_constant_produces_nothing(self):
        self.assertEqual(MutationProposer()._retune("skill_manage.py", "NO_SUCH", 1, 5, "up"), [])

    def test_proposal_targets_mutable_file(self):
        diffs = MutationProposer().propose({"type": "generic", "target": "COMPLEXITY_TOOL_CALLS"})
        self.assertTrue(diffs)
        self.assertTrue(_is_mutable(diffs[0].path)[0])


class SandboxTests(unittest.TestCase):
    """SLOW: copies the tree and runs subprocesses."""

    def test_sandbox_is_a_copy(self):
        real = (BACKEND / "skill_manage.py").read_text()
        with SandboxedRepo() as box:
            (box.root / "skill_manage.py").write_text("# clobbered\n")
            self.assertEqual((BACKEND / "skill_manage.py").read_text(), real,
                             "sandbox must never touch the real tree")

    def test_apply_rejects_stale_diff(self):
        with SandboxedRepo() as box:
            d = Diff("skill_manage.py", "THIS IS NOT THE FILE\n", "x = 1\n")
            r = box.apply([d])
            self.assertFalse(r["ok"])
            self.assertIn("drifted", r["errors"][0]["error"])

    def test_apply_rejects_syntax_error(self):
        with SandboxedRepo() as box:
            src = (BACKEND / "skill_manage.py").read_text()
            r = box.apply([Diff("skill_manage.py", src, "def broken(:\n")])
            self.assertFalse(r["ok"])
            self.assertIn("syntax", r["errors"][0]["error"].lower())

    def test_apply_rejects_protected_file(self):
        with SandboxedRepo() as box:
            src = (BACKEND / "evals.py").read_text()
            r = box.apply([Diff("evals.py", src, src + "\n# tampered\n")])
            self.assertFalse(r["ok"])

    def test_frozen_eval_runs_in_sandbox(self):
        with SandboxedRepo() as box:
            res = box.run_frozen_eval()
            self.assertTrue(res["ok"], f"baseline eval should run: {res}")
            self.assertGreaterEqual(res["score"], 0.9)


class CorruptCacheTests(unittest.TestCase):
    """
    Regression (pre-existing bug, surfaced by sandbox subprocesses): a truncated or
    empty vectors.json raised JSONDecodeError and took down agent startup entirely.
    A corrupt cache must degrade to an empty cache.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._old = os.environ.get("VORTEX_HOME")
        os.environ["VORTEX_HOME"] = str(self.tmp)

    def tearDown(self):
        if self._old is not None:
            os.environ["VORTEX_HOME"] = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_corrupt_vector_store_does_not_crash(self):
        from vector_memory import LocalVectorStore
        for junk in ("", "{", "not json at all", "null", '{"a":'):
            p = self.tmp / "vectors.json"
            p.write_text(junk)
            self.assertEqual(LocalVectorStore(p).docs, [], f"failed on {junk!r}")


class ApprovalQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.q = ApprovalQueue(home=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unverified_is_never_applied(self):
        """The core safety property: no verification, no write."""
        mid = self.q.submit({"verified": False, "diffs": [
            {"path": "skill_manage.py", "old_source": "x", "new_source": "y"}]})
        r = self.q.approve(mid, apply=True)
        self.assertIn("error", r)
        self.assertIn("unverified", r["error"])

    def test_approve_without_apply(self):
        mid = self.q.submit({"verified": True, "diffs": []})
        self.q.approve(mid, apply=False)
        self.assertEqual(self.q.get(mid)["state"], "approved_not_applied")

    def test_reject(self):
        mid = self.q.submit({"verified": True, "diffs": []})
        self.q.reject(mid, "not wanted")
        self.assertEqual(self.q.get(mid)["state"], "rejected")
        self.assertNotIn(mid, [p["id"] for p in self.q.list_pending()])

    def test_double_approve_blocked(self):
        mid = self.q.submit({"verified": True, "diffs": []})
        self.q.approve(mid, apply=False)
        self.assertIn("error", self.q.approve(mid, apply=True))

    def test_stale_source_not_applied(self):
        mid = self.q.submit({"verified": True, "diffs": [
            {"path": "skill_manage.py", "old_source": "NOT THE CURRENT FILE",
             "new_source": "x = 1\n"}]})
        r = self.q.approve(mid, apply=True)
        self.assertEqual(r["state"], "apply_failed")

    def test_rollback_needs_applied_state(self):
        mid = self.q.submit({"verified": True, "diffs": []})
        self.assertIn("error", self.q.rollback(mid))


@unittest.skipUnless(os.environ.get("VORTEX_SLOW_TESTS") == "1",
                     "full-pipeline tests copy the tree and run the whole suite in a "
                     "subprocess (~4 min each); set VORTEX_SLOW_TESTS=1 to run them")
class EndToEndTests(unittest.TestCase):
    """
    SLOW: the full pipeline, including a real write to the working tree.

    Skipped by default so the everyday suite stays fast. These are the tests that
    prove self-modification actually works end to end, so they are run explicitly
    (and were run when this feature landed).
    """

    def test_regression_is_rejected(self):
        """
        A mutation that breaks the suite must never be queued.
        Lowering COMPLEXITY_TOOL_CALLS to 1 breaks test_complexity_trigger.
        """
        ce = CodeEvolution()
        rec = ce.evolve_code({"type": "tuning", "target": "COMPLEXITY_TOOL_CALLS",
                              "direction": "down"})
        self.assertEqual(rec["decision"], "rejected")
        self.assertFalse(rec["verified"])
        self.assertIn("tests failed", rec["reason"])

    def test_good_mutation_applies_then_rolls_back(self):
        """Full loop: propose → verify → approve → file changes → rollback restores."""
        target = BACKEND / "profile_memory.py"
        original = target.read_text()
        ce = CodeEvolution()
        rec = ce.evolve_code({"type": "tuning", "target": "MEMORY_CAP", "direction": "up"})
        self.assertTrue(rec["verified"], f"expected verified, got {rec.get('reason')}")
        self.assertEqual(rec["candidate_eval"]["score"], rec["baseline_eval"]["score"])

        mid = [p for p in ce.queue.list_pending()][-1]["id"]
        try:
            res = ce.queue.approve(mid, apply=True)
            self.assertEqual(res["state"], "applied")
            self.assertNotEqual(target.read_text(), original, "file should have changed")
        finally:
            ce.queue.rollback(mid)
        self.assertEqual(target.read_text(), original, "rollback must restore exactly")


if __name__ == "__main__":
    unittest.main()
