"""Rapid self-improvement: mid-turn rescue, lessons, eval, promote."""
import os
import tempfile
import unittest

os.environ["VORTEX_HOME"] = tempfile.mkdtemp(prefix="vortex-rsi-")

from evals import run_suite  # noqa: E402
from memory import Memory  # noqa: E402
from self_improve import IntentCompiler, compile_fib, compile_math  # noqa: E402
from swarm import VortexAgent  # noqa: E402


class CompilerTests(unittest.TestCase):
    def test_math(self):
        self.assertEqual(compile_math("what is 12 times 8"), "print(12 * 8)")
        self.assertEqual(compile_math("sum of 40 and 2"), "print(40 + 2)")
        # chained arithmetic must keep the full expression (was: 45, dropping "+ 5")
        self.assertEqual(compile_math("what is 15 times 3 plus 5"), "print(15 * 3 + 5)")
        self.assertEqual(compile_math("calculate 100 divided by 4"), "print(100 / 4)")

    def test_fib(self):
        self.assertIn("print(fib(10))", compile_fib("fibonacci of 10"))

    def test_hide_intent(self):
        hit = IntentCompiler.compile("hide password | weather report")
        self.assertEqual(hit["tool"], "steganography")
        self.assertEqual(hit["args"]["payload"], "password")


class RSIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.memory = Memory()
        cls.agent = VortexAgent(cls.memory)

    def test_improver_spawned(self):
        names = {b["name"] for b in self.agent.list_bots()}
        self.assertIn("improver", names)

    def test_nl_math_compiles_in_turn(self):
        reply = self.agent.chat("what is 12 times 8")
        self.assertIn("96", reply)

    def test_chained_math_in_turn(self):
        reply = self.agent.chat("what is 15 times 3 plus 5")
        self.assertIn("50", reply)

    def test_fibonacci_of_n(self):
        reply = self.agent.chat("fibonacci of 10")
        self.assertIn("55", reply)

    def test_slash_run(self):
        reply = self.agent.chat("/run print(3+4)")
        self.assertIn("7", reply)

    def test_lessons_and_traces_recorded(self):
        self.agent.chat("sum of 21 and 21")
        traces = self.memory.get_traces(20)
        self.assertTrue(traces)
        self.assertTrue(any(t["score"] and t["score"] >= 0.8 for t in traces))
        lessons = self.memory.get_lessons(True)
        self.assertTrue(lessons)

    def test_tool_retry_wraps_syntax(self):
        result = self.agent.rsi.retry_tool(
            "codeforge", {"code": "1+2"}, "Syntax error: invalid syntax")
        self.assertIsNotNone(result)
        res, mutated = result
        self.assertEqual(res.status, "success")
        self.assertIn("print", mutated["code"])
        self.assertIn("3", res.data.get("output", ""))

    def test_eval_suite_mostly_passes(self):
        out = run_suite(self.agent, persist=True, name="unit")
        self.assertGreaterEqual(out["passed"], 5)
        self.assertGreaterEqual(out["score"], 0.6)

    def test_cycle_promotes_or_holds(self):
        cycle = self.agent.rsi.run_cycle()
        self.assertIn(cycle["decision"], ("promoted", "reverted"))
        self.assertGreaterEqual(self.memory.current_generation(), 1)
        report = self.agent.rsi.report()
        self.assertIn("RSI generation", report)


if __name__ == "__main__":
    unittest.main()
