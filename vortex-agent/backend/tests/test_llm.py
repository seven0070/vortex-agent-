"""
Phase 3 tests — LLM layer + reasoning wiring.

Runs fully offline: a fake transport stands in for the network, so these tests
verify the live-model code path without keys, without HTTP, and deterministically.
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import llm as llm_mod
from llm import LLM, extract_json, get_llm, reset_llm, set_llm


def openai_transport(reply_text):
    """Fake OpenAI-compatible endpoint returning a fixed assistant message."""
    def _t(url, payload, headers):
        _t.calls.append({"url": url, "payload": payload, "headers": headers})
        return {"choices": [{"message": {"role": "assistant", "content": reply_text}}]}
    _t.calls = []
    return _t


def anthropic_transport(reply_text):
    def _t(url, payload, headers):
        _t.calls.append({"url": url, "payload": payload, "headers": headers})
        return {"content": [{"type": "text", "text": reply_text}]}
    _t.calls = []
    return _t


def failing_transport(exc=RuntimeError("connection refused")):
    def _t(url, payload, headers):
        raise exc
    return _t


class LLMClientTests(unittest.TestCase):
    def tearDown(self):
        reset_llm()

    def test_unconfigured_is_unavailable(self):
        """No provider -> unavailable, and completion fails soft rather than raising."""
        client = LLM(provider=None, api_key="", base_url="", model="")
        self.assertFalse(client.available)
        r = client.complete("sys", "hello")
        self.assertFalse(bool(r))
        self.assertEqual(r.error, "llm_not_configured")

    def test_openai_shape_and_extraction(self):
        t = openai_transport("Hello from the model.")
        client = LLM(provider="openai", api_key="k", model="gpt-4o-mini", transport=t)
        self.assertTrue(client.available)
        r = client.complete("You are terse.", "hi")
        self.assertTrue(bool(r))
        self.assertEqual(r.text, "Hello from the model.")
        body = t.calls[0]["payload"]
        self.assertEqual(body["model"], "gpt-4o-mini")
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertIn("chat/completions", t.calls[0]["url"])

    def test_anthropic_shape_hoists_system(self):
        t = anthropic_transport("Anthropic reply.")
        client = LLM(provider="anthropic", api_key="k",
                     model="claude-3-5-sonnet-20241022", transport=t)
        r = client.complete("BE TERSE", "hi")
        self.assertEqual(r.text, "Anthropic reply.")
        body = t.calls[0]["payload"]
        self.assertEqual(body["system"], "BE TERSE")
        self.assertTrue(all(m["role"] != "system" for m in body["messages"]))

    def test_failure_is_soft_and_counted(self):
        client = LLM(provider="openai", api_key="k", model="m", transport=failing_transport())
        r = client.complete("s", "u")
        self.assertFalse(bool(r))
        self.assertIn("connection refused", r.error)
        self.assertEqual(client.failures, 1)

    def test_empty_response_is_not_ok(self):
        client = LLM(provider="openai", api_key="k", model="m", transport=openai_transport("   "))
        self.assertFalse(bool(client.complete("s", "u")))

    def test_complete_json_handles_fences(self):
        t = openai_transport('```json\n{"tool": "codeforge", "args": {"code": "print(1)"}}\n```')
        client = LLM(provider="openai", api_key="k", model="m", transport=t)
        data = client.complete_json("s", "u")
        self.assertEqual(data["tool"], "codeforge")

    def test_extract_json_variants(self):
        self.assertEqual(extract_json('{"a": 1}')["a"], 1)
        self.assertEqual(extract_json('prose then {"a": 2} trailing')["a"], 2)
        self.assertEqual(extract_json('```json\n{"a": 3}\n```')["a"], 3)
        self.assertIsNone(extract_json("no json at all"))
        self.assertIsNone(extract_json(""))

    def test_status_reports_mode(self):
        self.assertEqual(LLM(provider=None, api_key="", base_url="", model="").status()["mode"],
                         "deterministic-fallback")
        live = LLM(provider="openai", api_key="k", model="m", transport=openai_transport("x"))
        self.assertEqual(live.status()["mode"], "live")


class ReasoningTests(unittest.TestCase):
    def tearDown(self):
        reset_llm()

    def _install(self, reply):
        set_llm(LLM(provider="openai", api_key="k", model="m", transport=openai_transport(reply)))

    def test_route_returns_none_without_llm(self):
        reset_llm()
        set_llm(LLM(provider=None, api_key="", base_url="", model=""))
        from reasoning import llm_route
        self.assertIsNone(llm_route("what is 2+2"))

    def test_route_selects_codeforge(self):
        self._install(json.dumps({"tool": "codeforge",
                                  "args": {"code": "print(6*7)"}, "reason": "math"}))
        from reasoning import llm_route
        route = llm_route("what is six times seven")
        self.assertIsNotNone(route)
        self.assertEqual(route[0], "codeforge")
        self.assertIn("print", route[1]["code"])

    def test_route_rejects_unknown_tool(self):
        self._install(json.dumps({"tool": "definitely_not_a_tool", "args": {}}))
        from reasoning import llm_route
        self.assertIsNone(llm_route("do a thing"))

    def test_route_accepts_no_tool(self):
        self._install(json.dumps({"tool": None, "args": {}, "reason": "chat"}))
        from reasoning import llm_route
        self.assertIsNone(llm_route("how are you feeling today"))

    def test_route_rejects_empty_code(self):
        self._install(json.dumps({"tool": "codeforge", "args": {"code": "   "}}))
        from reasoning import llm_route
        self.assertIsNone(llm_route("compute something"))

    def test_route_survives_garbage(self):
        self._install("this is not json at all")
        from reasoning import llm_route
        self.assertIsNone(llm_route("anything"))

    def test_route_ignores_memory_context(self):
        """
        Regression: recalled memory must never reach the router prompt.

        Leaking it let a previous turn hijack the current decision — after a word
        problem, an unrelated "who are you?" re-ran the arithmetic and printed 65.
        """
        captured = {}

        def transport(url, payload, headers):
            captured["user"] = payload["messages"][-1]["content"]
            return {"choices": [{"message": {"content": json.dumps({"tool": None, "args": {}})}}]}

        set_llm(LLM(provider="openai", api_key="k", model="m", transport=transport))
        from reasoning import llm_route
        poison = ["[architect/coding] 7 baskets 12 apples give away 19 -> Output: 65"]
        llm_route("who are you?", "research", poison)
        self.assertNotIn("65", captured["user"])
        self.assertNotIn("baskets", captured["user"])
        self.assertIn("who are you?", captured["user"])

    def test_role_reply_used_when_available(self):
        self._install("The auth module has a token refresh race condition.")
        from reasoning import llm_role_reply
        out = llm_role_reply("coding", "architect", "review auth")
        self.assertIn("race condition", out)
        self.assertIn("Architect", out)

    def test_council_analysis_parses(self):
        self._install(json.dumps({"analysis": "Risk is concentrated in the retry path.",
                                  "evidence": ["retry has no backoff"], "confidence": 0.82}))
        from reasoning import llm_council_analysis
        got = llm_council_analysis("Critic", "You challenge proposals.", "ship the retry fix", "proposal")
        self.assertEqual(got["confidence"], 0.82)
        self.assertIn("retry path", got["analysis"])

    def test_council_confidence_is_clamped(self):
        self._install(json.dumps({"analysis": "ok", "evidence": [], "confidence": 99}))
        from reasoning import llm_council_analysis
        self.assertEqual(llm_council_analysis("Critic", "p", "g", "prop")["confidence"], 1.0)


class SwarmIntegrationTests(unittest.TestCase):
    """The wiring actually changes agent behaviour — and degrades cleanly."""

    @classmethod
    def setUpClass(cls):
        os.environ["VORTEX_HOME"] = "/tmp/vortex-llm-test"

    def tearDown(self):
        reset_llm()

    def test_agent_works_without_llm(self):
        """Baseline: no provider -> deterministic path still answers correctly."""
        set_llm(LLM(provider=None, api_key="", base_url="", model=""))
        from memory import Memory
        from swarm import VortexAgent
        agent = VortexAgent(Memory())
        self.assertIn("84", agent.chat("what is 12 * 7"))

    def test_llm_routing_reaches_the_tool(self):
        """A model-chosen route is executed and its output returned."""
        set_llm(LLM(provider="openai", api_key="k", model="m",
                    transport=openai_transport(json.dumps({
                        "tool": "codeforge",
                        "args": {"code": "print('routed-by-model')"}}))))
        from memory import Memory
        from swarm import VortexAgent
        agent = VortexAgent(Memory())
        self.assertIn("routed-by-model", agent.bots["architect"].handle("do the thing"))

    def test_no_stale_phase3_disclaimer(self):
        """The old 'no live LLM wired yet (that's Phase 3)' text is gone for good."""
        src = (Path(__file__).resolve().parent.parent / "orchestrator.py").read_text()
        self.assertNotIn("that's Phase 3", src)


if __name__ == "__main__":
    unittest.main()
