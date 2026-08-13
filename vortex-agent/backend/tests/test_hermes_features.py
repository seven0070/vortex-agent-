"""
Tests for the Hermes-inspired capabilities Vortex was missing:
  1. cross-session recall (FTS5)       — sessions.py
  2. guaranteed context MEMORY/USER.md — profile_memory.py
  3. autonomous skill creation         — skill_manage.py

All offline and deterministic — none of these features require an LLM.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        from sessions import SessionStore
        self.conn = sqlite3.connect(":memory:")
        self.store = SessionStore(self.conn)

    def test_fts5_backend_selected(self):
        self.assertEqual(self.store.stats()["search_backend"], "fts5")

    def test_record_and_search_across_sessions(self):
        s1 = self.store.start("first")
        self.store.record("user", "we decided to add exponential backoff to the retry path")
        self.store.record("assistant", "noted, backoff added")
        self.store.end("done", s1)

        s2 = self.store.start("second")
        self.store.record("user", "totally unrelated chat about pizza toppings")

        hits = self.store.search("exponential backoff retry")
        self.assertTrue(hits, "expected a cross-session hit")
        self.assertTrue(any("backoff" in h["content"] for h in hits))
        self.assertTrue(any(h["session_id"] == s1 for h in hits))

    def test_exclude_current_session(self):
        s1 = self.store.start("old")
        self.store.record("user", "kubernetes ingress configuration notes")
        self.store.start("new")
        self.store.record("user", "kubernetes ingress again today")
        hits = self.store.search("kubernetes ingress", exclude_current=True)
        self.assertTrue(all(h["session_id"] == s1 for h in hits))

    def test_search_survives_punctuation(self):
        """FTS5 MATCH throws on raw punctuation — sanitiser must prevent that."""
        self.store.start()
        self.store.record("user", "the retry bug is fixed")
        for q in ['what about "retry"?', "retry -- bug!", "(retry)", "a'b retry"]:
            self.assertIsInstance(self.store.search(q), list)

    def test_empty_query_and_no_match(self):
        self.store.start()
        self.store.record("user", "hello")
        self.assertEqual(self.store.search(""), [])
        self.assertEqual(self.store.search("zzzznonexistentterm"), [])

    def test_empty_content_not_recorded(self):
        self.store.start()
        self.assertIsNone(self.store.record("user", "   "))

    def test_get_session_returns_transcript(self):
        sid = self.store.start("t")
        self.store.record("user", "one")
        self.store.record("assistant", "two")
        got = self.store.get_session(sid)
        self.assertEqual(got["turns"], 2)
        self.assertEqual([m["content"] for m in got["messages"]], ["one", "two"])

    def test_like_fallback_when_no_fts(self):
        """Feature must still work on a SQLite build without FTS5."""
        from sessions import SessionStore
        conn = sqlite3.connect(":memory:")
        store = SessionStore(conn)
        store.fts = False  # simulate missing FTS5
        store.start()
        store.record("user", "the caching layer needs invalidation")
        hits = store.search("caching invalidation")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["match"], "like")


class ProfileMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        from profile_memory import ProfileMemory
        self.p = ProfileMemory(home=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_files_created(self):
        self.assertTrue((self.tmp / "MEMORY.md").exists())
        self.assertTrue((self.tmp / "USER.md").exists())

    def test_remember_and_context_block(self):
        self.p.remember_user("Name: Ada")
        self.p.remember("Uses: FastAPI and SQLite")
        block = self.p.context_block()
        self.assertIn("Ada", block)
        self.assertIn("FastAPI", block)

    def test_empty_context_costs_nothing(self):
        self.assertEqual(self.p.context_block(), "")

    def test_dedupe(self):
        self.assertTrue(self.p.remember("Uses: Postgres")["written"])
        r = self.p.remember("uses: postgres.")
        self.assertFalse(r["written"])
        self.assertEqual(r["reason"], "duplicate")

    def test_cap_enforced_by_eviction(self):
        """Always-in-context files must never grow unbounded."""
        from profile_memory import MEMORY_CAP
        for i in range(300):
            self.p.remember(f"Fact number {i} with some padding text to consume budget")
        self.assertLessEqual(len(self.p.read_memory()), MEMORY_CAP)
        # newest survives, oldest evicted
        self.assertIn("299", self.p.read_memory())
        self.assertNotIn("Fact number 0 ", self.p.read_memory())

    def test_forget(self):
        self.p.remember("Uses: Redis")
        self.p.remember("Uses: Kafka")
        self.assertEqual(self.p.forget("Redis")["removed"], 1)
        self.assertNotIn("Redis", self.p.read_memory())
        self.assertIn("Kafka", self.p.read_memory())

    def test_hand_editable(self):
        """Files are plain markdown a human can edit — like Hermes."""
        (self.tmp / "MEMORY.md").write_text("# MEMORY.md\n\n- Hand written fact\n")
        self.assertIn("Hand written fact", self.p.context_block())


class FactExtractionTests(unittest.TestCase):
    def test_user_facts(self):
        from profile_memory import extract_profile_facts
        got = extract_profile_facts("Hi, my name is Ada and I work at Analytical Engines.")
        joined = " ".join(got["user"])
        self.assertIn("Ada", joined)
        self.assertIn("Analytical Engines", joined)

    def test_name_stops_at_clause_boundary(self):
        """
        Regression: "my name is Ravi and I work at Acme" stored the whole tail as the
        name ("Name: Ravi and I work at Acme Robotics"). Guaranteed context is only
        useful if it is clean.
        """
        from profile_memory import extract_profile_facts
        names = [f for f in extract_profile_facts(
            "my name is Ravi and I work at Acme Robotics")["user"] if f.startswith("Name:")]
        self.assertEqual(names, ["Name: Ravi"])

    def test_surname_still_captured(self):
        from profile_memory import extract_profile_facts
        names = [f for f in extract_profile_facts("my name is Ada Lovelace.")["user"]
                 if f.startswith("Name:")]
        self.assertEqual(names, ["Name: Ada Lovelace"])

    def test_no_duplicate_name_facts(self):
        from profile_memory import extract_profile_facts
        names = [f for f in extract_profile_facts("my name is Bob, I am a developer")["user"]
                 if f.startswith("Name:")]
        self.assertEqual(len(names), 1)

    def test_memory_facts(self):
        from profile_memory import extract_profile_facts
        got = extract_profile_facts("Remember that the deploy script needs sudo.")
        self.assertTrue(any("deploy script" in f for f in got["memory"]))

    def test_conventions(self):
        from profile_memory import extract_profile_facts
        self.assertTrue(any("never" in f.lower()
                            for f in extract_profile_facts("Never force push to main.")["memory"]))

    def test_no_false_positives(self):
        from profile_memory import extract_profile_facts
        got = extract_profile_facts("what is 2 + 2?")
        self.assertEqual(got["user"], [])
        self.assertEqual(got["memory"], [])

    def test_oversized_input_ignored(self):
        from profile_memory import extract_profile_facts
        got = extract_profile_facts("my name is Ada. " + "x" * 5000)
        self.assertEqual(got, {"user": [], "memory": []})


class SkillManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["VORTEX_HOME"] = cls.tmp

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _agent(self):
        from memory import Memory
        from swarm import VortexAgent
        return VortexAgent(Memory())

    def test_complexity_trigger(self):
        from skill_manage import SkillManager
        self.assertTrue(SkillManager.is_complex(tool_calls=2))
        self.assertTrue(SkillManager.is_complex(steps=2))
        self.assertTrue(SkillManager.is_complex(tool_calls=1, rescued=True))
        self.assertTrue(SkillManager.is_complex(tool_calls=1, retried=True))
        self.assertFalse(SkillManager.is_complex(tool_calls=1))
        self.assertFalse(SkillManager.is_complex())

    def test_slugify(self):
        from skill_manage import slugify
        self.assertEqual(slugify("Please benchmark the fibonacci sequence"),
                         "benchmark_fibonacci_sequence")
        self.assertEqual(slugify(""), "task")

    def test_capture_creates_then_improves(self):
        agent = self._agent()
        sm = agent.skill_manager
        first = sm.capture("benchmark fibonacci performance", ["step a", "step b", "step c"])
        self.assertIsNotNone(first)
        self.assertEqual(first["uses"], 1)

        second = sm.capture("benchmark fibonacci performance", ["step c", "step d"])
        self.assertEqual(second["uses"], 2, "same goal should improve, not duplicate")
        self.assertIn("step d", second["steps"])
        self.assertEqual(len([s for s in second["steps"] if s == "step c"]), 1, "steps deduped")

    def test_capture_needs_steps(self):
        agent = self._agent()
        self.assertIsNone(agent.skill_manager.capture("goal", []))

    def test_find_relevant_skill(self):
        agent = self._agent()
        agent.skill_manager.capture("deploy the staging cluster", ["a", "b", "c"])
        self.assertIsNotNone(agent.skill_manager.find("deploy staging cluster now"))
        self.assertIsNone(agent.skill_manager.find("completely different unrelated topic"))

    def test_skill_persisted_to_library(self):
        agent = self._agent()
        agent.skill_manager.capture("compress the archive files", ["x", "y", "z"])
        self.assertIn("compress_archive_files", [s.get("name") for s in agent.skills.list()])


class IntegrationTests(unittest.TestCase):
    """The features are wired into the real agent turn loop."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["VORTEX_HOME"] = cls.tmp

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_chat_records_session_and_is_searchable(self):
        from memory import Memory
        from swarm import VortexAgent
        agent = VortexAgent(Memory())
        agent.chat("what is 11 * 11")
        hits = agent.recall_sessions("11")
        self.assertTrue(hits, "chat turns should be searchable across sessions")

    def test_chat_captures_user_profile(self):
        from memory import Memory
        from swarm import VortexAgent
        agent = VortexAgent(Memory())
        agent.chat("my name is Grace and I prefer concise answers")
        block = agent.memory.profile.context_block()
        self.assertIn("Grace", block)

    def test_multi_bot_turn_creates_a_skill(self):
        """
        Regression: the complexity bar was copied from Hermes (5+ tool calls) and never
        fired, because Vortex's compiler collapses work into one call and multi-bot
        work shows up as delegations. A two-specialist plan must produce a skill.
        """
        from memory import Memory
        from swarm import VortexAgent
        agent = VortexAgent(Memory())
        before = agent.skill_manager.stats()["auto_created"]
        agent.chat("analyze the caching layer and build a prototype")
        self.assertGreater(agent.skill_manager.stats()["auto_created"], before)

    def test_memory_exposes_new_layers(self):
        from memory import Memory
        m = Memory()
        self.assertIsNotNone(m.sessions)
        self.assertIsNotNone(m.profile)


if __name__ == "__main__":
    unittest.main()
