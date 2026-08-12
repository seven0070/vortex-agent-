"""One request must travel the intended control layers. Nothing bypasses them."""
import os
import tempfile
import unittest

os.environ["VORTEX_HOME"] = tempfile.mkdtemp(prefix="vortex-1-int-")

from memory import Memory  # noqa: E402
from swarm import VortexAgent  # noqa: E402


REQUIRED = (
    "interface", "sovereign", "governance", "orchestration",
    "resolution", "memory", "evaluation", "self-improvement",
)


class RequestPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.memory = Memory()
        cls.agent = VortexAgent(cls.memory)

    def test_simple_request_hits_every_control_layer(self):
        reply = self.agent.chat("what is 12 times 8")
        self.assertIn("96", reply)
        rec = self.agent.last_pipeline or {}
        layers = rec.get("layers") or []
        for name in REQUIRED:
            self.assertTrue(any(name in layer for layer in layers), f"missing {name} in {layers}")
        for key in ("trace_id", "generation", "route", "memory_hits",
                    "tool_calls", "latency_ms", "evaluation_score"):
            self.assertIn(key, rec)
        self.assertIsNotNone(self.agent.sovereign)
        self.assertIsNotNone(self.agent.governance)
        self.assertIsNotNone(self.agent.council)
        self.assertIsNotNone(self.agent.resolver)
        self.assertIsNotNone(self.agent.observability)
        self.assertIsNotNone(self.agent.memory.graph or self.agent.memory.kg)

    def test_dangerous_request_stopped_by_governance(self):
        reply = self.agent.chat("rm -rf /")
        self.assertIn("DENY", reply)
        self.assertEqual((self.agent.last_pipeline or {}).get("denied"), True)

    def test_memory_and_graph_store_the_turn(self):
        self.agent.memory.remember("Vortex 1.0 validation token ALPHA-ZULU", kind="fact")
        reply = self.agent.chat("what is the Vortex 1.0 validation token ALPHA-ZULU")
        self.assertIn("ALPHA-ZULU", reply)


if __name__ == "__main__":
    unittest.main()
