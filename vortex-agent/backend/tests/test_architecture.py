"""Test full Vortex architecture upgrade."""
import tempfile, os
os.environ['VORTEX_HOME'] = tempfile.mkdtemp(prefix='vortex-arch-')

import unittest

class ArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from memory import Memory
        from swarm import VortexAgent
        cls.memory = Memory()
        cls.agent = VortexAgent(cls.memory)

    def test_memory_layers(self):
        m = self.memory
        # working memory
        m.working.add("test working", kind="test")
        self.assertTrue(len(m.working.get_context())>0)
        # semantic
        m.semantic.remember_fact("Vortex is a self-improving agent", kind="fact")
        rec = m.semantic.recall_facts("Vortex", n=2)
        self.assertTrue(rec)
        # episodic
        m.episodic.remember_event("test event", kind="test")
        eps = m.episodic.recall_events(query="test", limit=5)
        self.assertTrue(len(eps)>=1)
        # user memory
        m.user.remember_user("pref_test", "value123")
        self.assertEqual(m.user.recall_user("pref_test"), "value123")
        # agent memory
        m.agent_memory.remember("researcher", "learned something", kind="learning")
        am = m.agent_memory.recall("researcher", query="learned", limit=2)
        self.assertTrue(am)
        # knowledge graph
        if m.graph:
            kg_res = m.graph.remember("researcher uses codeforge to benchmark fibonacci", kind="fact")
            self.assertIn("nodes", kg_res)
            recall = m.graph.recall("fibonacci", n=3)
            self.assertTrue(recall)
            # forget / improve
            m.graph.forget(label="fibonacci", decay=True)
            imp = m.graph.improve()
            self.assertIn("merged", imp)

    def test_orchestration_state(self):
        from orchestration import VortexState, StateManager, create_default_graph
        state = VortexState(goal="test goal")
        t = state.add_task(goal="subtask 1", description="desc", assigned_to="Researcher")
        self.assertEqual(t.goal, "subtask 1")
        state.transition(state.phase, "test")
        mgr = StateManager()
        mgr.save(state)
        loaded = mgr.load(state.run_id)
        self.assertEqual(loaded.goal, "test goal")

    def test_orchestration_graph(self):
        from orchestration import create_default_graph
        # fast run
        graph = create_default_graph(agent=self.agent, memory=self.memory, tools=self.agent.tool_registry.tools)
        state = graph.run(goal="calculate 6 times 7", generation=0)
        self.assertIsNotNone(state.final_response)
        self.assertIn("42", state.final_response or "")

    def test_council(self):
        self.assertIsNotNone(self.agent.council)
        deliberation = self.agent.council.deliberate(goal="research fibonacci")
        self.assertIn("decision", deliberation)
        self.assertIn("final", deliberation)
        self.assertGreater(deliberation.get("confidence",0), 0.2)

    def test_resolution(self):
        self.assertIsNotNone(self.agent.resolver)
        candidates = [
            {"id": "a", "result": "96", "confidence": 0.9, "latency_ms": 10},
            {"id": "b", "result": "error", "confidence": 0.2, "latency_ms": 100},
        ]
        res = self.agent.resolver.resolve(candidates, goal="what is 12 times 8")
        self.assertIn("selected", res)
        self.assertEqual(res["action"], "select")

    def test_governance(self):
        self.assertIsNotNone(self.agent.governance)
        dec = self.agent.governance.evaluate(task="research fibonacci", context={}, agent="researcher", action="execute")
        self.assertIn(dec["action"], ("ALLOW","ESCALATE","DENY"))
        # dangerous should deny
        dec2 = self.agent.governance.evaluate(task="rm -rf /", context={}, agent="chief", action="execute")
        self.assertEqual(dec2["action"], "DENY")

    def test_sovereign(self):
        self.assertIsNotNone(self.agent.sovereign)
        ctx = self.agent.sovereign.context()
        self.assertIn("identity", ctx)
        self.assertIn("objectives", ctx)
        who = self.agent.sovereign.identity.whoami()
        self.assertIn("Vortex", who)

    def test_tools_registry(self):
        self.assertIsNotNone(self.agent.tool_registry)
        lst = self.agent.tool_registry.list()
        self.assertTrue(len(lst) >= 3)
        cats = self.agent.tool_registry.categories()
        self.assertIn("code", cats or {})

    def test_observability(self):
        self.assertIsNotNone(self.agent.observability)
        trace_id = self.agent.observability.tracer.start_trace("test trace")
        span_id = self.agent.observability.tracer.start_span(trace_id, "test span")
        self.agent.observability.tracer.finish_span(span_id)
        trace = self.agent.observability.tracer.finish_trace(trace_id, final_outcome="ok", score=0.9)
        self.assertIsNotNone(trace)
        self.agent.observability.metrics.inc("test_counter")
        summ = self.agent.observability.metrics.summary()
        self.assertIn("counters", summ)

    def test_benchmark(self):
        from evals import VortexBenchmark, run_suite
        suite = run_suite(self.agent, persist=False)
        self.assertGreaterEqual(suite["score"], 0.5)
        vb = VortexBenchmark(self.agent)
        comp = vb.run_comprehensive(persist=False)
        self.assertGreaterEqual(comp["score"], 0.5)
        comparison = vb.compare(suite, comp)
        self.assertIn("diff_by_category", comparison)

    def test_evolution_engine(self):
        evo = self.agent.rsi.evolution
        self.assertIsNotNone(evo)
        obs = evo.observe()
        self.assertIn("traces", obs)
        weaknesses = evo.find_weaknesses()
        self.assertTrue(isinstance(weaknesses, list))
        rec = evo.evolve_once()
        self.assertIn(rec.get("decision"), ("promoted", "rejected", "canary_failed", "reject"))
        self.assertNotIn("sandbox tests passed (mock)", str(rec.get("sandbox_result")))
        if rec.get("decision") == "promoted":
            from self_improve import compile_math
            self.assertIn("+ 5", compile_math("what is 15 times 3 plus 5") or "")

    def test_pipeline_is_wired(self):
        self.assertIsNotNone(self.agent.pipeline)
        self.agent.chat("who are you")
        self.assertTrue(self.agent.last_pipeline)
        layers = self.agent.last_pipeline.get("layers") or []
        self.assertIn("sovereign", layers)
        self.assertIn("governance", layers)

if __name__ == "__main__":
    unittest.main()
