"""VortexOS — owns sessions, swarm, council, skills, memory, autonomy (the waist)."""
from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional, Set

from vortex.agent.council import AgentCouncil
from vortex.agent.llm import LLMBrain
from vortex.agent.memory_provider import BuiltinMemory
from vortex.agent.run_agent import AIAgent
from vortex.agent.skills import SkillHub
from vortex.agent.state import SessionDB
from vortex.agent.vector_memory import VectorMemory
from vortex.constants import ensure_home
from vortex.tools.registry import registry
import vortex.tools  # noqa: F401


class VortexBot:
    """Thin specialist wrapper around a role-scoped AIAgent."""

    def __init__(self, os: "VortexOS", name: str, role: str, toolset: str):
        self.os = os
        self.name = name
        self.role = role
        self.toolset = toolset
        self.message_count = 0

    def handle(self, message: str) -> str:
        self.message_count += 1
        agent = AIAgent(
            session_db=self.os.db,
            vector=self.os.vector,
            skills=self.os.skills,
            memory_provider=self.os.memory,
            toolsets=[self.toolset],
            max_steps=8,
            event_cb=self.os._fanout,
            role=f"{self.name}:{self.role}",
            brain=self.os.brain,
            council=self.os.council,
        )
        result = agent.run(message, background=False)
        return result.get("result") or result.get("error") or "(empty)"


class VortexOS:
    """
    The OS layer:
      - shared SessionDB / vector / skills / memory
      - swarm of role bots
      - Agent Council (deliberate → vote → execute)
      - primary AIAgent for autonomous missions
      - event bus for UI / gateway
    """

    def __init__(self):
        ensure_home()
        self.db = SessionDB()
        self.vector = VectorMemory()
        self.skills = SkillHub()
        self.memory = BuiltinMemory()
        self.brain = LLMBrain()
        self._listeners: List[Callable[[dict], None]] = []
        self._lock = threading.Lock()

        # Council first (executor + seat worker factories close over OS state)
        self.council = AgentCouncil(
            session_db=self.db,
            vector=self.vector,
            skills=self.skills,
            memory_provider=self.memory,
            brain=self.brain,
            event_cb=self._fanout,
            executor_factory=self._make_executor,
            seat_worker_factory=self._make_seat_worker,
            use_chamber=True,
        )

        # primary autonomous agent (full toolset + council tools)
        self.agent = AIAgent(
            session_db=self.db,
            vector=self.vector,
            skills=self.skills,
            memory_provider=self.memory,
            toolsets=["full"],
            max_steps=12,
            event_cb=self._fanout,
            role="chief",
            brain=self.brain,
            council=self.council,
        )
        self.auto = self.agent

        self.bots: Dict[str, VortexBot] = {}
        for name, role, ts in [
            ("chief", "orchestrator", "full"),
            ("researcher", "research", "research"),
            ("architect", "coding", "coding"),
            ("cipher", "security", "security"),
            ("scout", "scout", "role_scout"),
        ]:
            self.spawn_bot(name, role, ts, quiet=True)

    def _make_executor(self) -> AIAgent:
        """Chief merge agent after chamber workers finish (no recursive council)."""
        return AIAgent(
            session_db=self.db,
            vector=self.vector,
            skills=self.skills,
            memory_provider=self.memory,
            toolsets=["core", "crypto", "files", "memory"],
            max_steps=10,
            event_cb=self._fanout,
            role="chief-merge",
            brain=self.brain,
            council=None,
            blocked_tools={"convene_council", "delegate_task"},
        )

    def _make_seat_worker(
        self,
        toolset: str = "core",
        role: str = "seat",
        blocked: Optional[set] = None,
    ) -> AIAgent:
        """Parallel chamber worker — one seat, scoped toolset, no council recursion."""
        blocked_tools = set(blocked or set()) | {"convene_council"}
        # Map single toolset names; allow composed presets
        ts = toolset or "core"
        toolsets = [ts]
        # Ensure workers always have files+memory for artifacts
        if ts not in ("full", "core"):
            toolsets = [ts, "files", "memory", "meta"]
        return AIAgent(
            session_db=self.db,
            vector=self.vector,
            skills=self.skills,
            memory_provider=self.memory,
            toolsets=toolsets,
            max_steps=6,
            event_cb=self._fanout,
            role=role,
            brain=self.brain,
            council=None,
            blocked_tools=blocked_tools,
        )

    # ── event bus ──────────────────────────────────────────────────────────
    def subscribe(self, cb: Callable[[dict], None]):
        self._listeners.append(cb)
        self.agent.event_cb = self._fanout
        self.council.event_cb = self._fanout

    def unsubscribe(self, cb: Callable[[dict], None]):
        if cb in self._listeners:
            self._listeners.remove(cb)

    def _fanout(self, event: dict):
        for cb in list(self._listeners):
            try:
                cb(event)
            except Exception:
                pass

    # ── swarm ──────────────────────────────────────────────────────────────
    def spawn_bot(self, name: str, role: str = "general", toolset: str = "core", quiet: bool = False):
        self.bots[name] = VortexBot(self, name, role, toolset)
        self.db.log_event("spawn", name)
        if not quiet:
            print(f"   ✨ Spawned {name} ({role}/{toolset})")
        return self.bots[name]

    def kill_bot(self, name: str) -> bool:
        if name in self.bots:
            del self.bots[name]
            self.db.log_event("kill", name)
            return True
        return False

    def list_bots(self) -> List[dict]:
        return [
            {
                "name": b.name,
                "role": b.role,
                "messages": b.message_count,
                "status": "active",
                "toolset": b.toolset,
            }
            for b in self.bots.values()
        ]

    # ── chat / missions / council ──────────────────────────────────────────
    def chat(self, message: str) -> str:
        self.db.add_message("main", "user", message)
        low = (message or "").lower().strip()

        # direct @bot
        if message.startswith("@"):
            name, _, rest = message[1:].partition(" ")
            if name in self.bots:
                reply = self.bots[name].handle(rest)
                self.db.add_message("main", f"bot:{name}", reply)
                return reply
            return f"Unknown bot '{name}'. Active: {', '.join(self.bots)}"

        # explicit council
        if low.startswith("/council ") or low.startswith("/deliberate "):
            goal = message.split(" ", 1)[1].strip()
            result = self.council.convene(goal, auto_execute=True, background=False)
            reply = self._format_council(result)
            self.db.add_message("main", "assistant", reply)
            return reply

        if low in ("/council", "/seats"):
            seats = self.council.list_seats()
            lines = ["⚖ Council seats:"]
            for s in seats:
                lines.append(
                    f"  {s['icon']} {s['name']} — {s['title']} (w={s['weight']})"
                )
            reply = "\n".join(lines)
            self.db.add_message("main", "assistant", reply)
            return reply

        # auto-council for high-stakes / multi-domain goals
        if self._wants_council(low):
            result = self.council.convene(message, auto_execute=True, background=False)
            reply = self._format_council(result)
            self.db.add_message("main", "assistant", reply)
            return reply

        reply = self.agent.chat(message)
        self.db.add_message("main", "assistant", reply)
        return reply

    @staticmethod
    def _wants_council(low: str) -> bool:
        if low.startswith("/auto "):
            return False
        triggers = (
            "council",
            "deliberate",
            "debate",
            "should we",
            "weigh the options",
            "pros and cons",
            "multi-step strategy",
            "high stakes",
            "architecture decision",
            "review this plan",
            "committee",
            "vote on",
        )
        if any(t in low for t in triggers):
            return True
        # multi-domain: research + build + secure language together
        domains = 0
        if any(k in low for k in ("research", "analyze", "investigate", "report")):
            domains += 1
        if any(k in low for k in ("build", "implement", "architect", "code", "design")):
            domains += 1
        if any(k in low for k in ("secure", "risk", "safety", "privacy", "threat")):
            domains += 1
        if any(k in low for k in ("strategy", "roadmap", "plan a", "decide")):
            domains += 1
        return domains >= 2

    @staticmethod
    def _format_council(result: dict) -> str:
        d = result.get("directive") or {}
        ex = result.get("execution") or {}
        decision = (d.get("decision") or result.get("status") or "?").upper()
        header = (
            f"⚖ Council [{result.get('id')}] — {result.get('status')} · "
            f"decision={decision}"
        )
        body = ex.get("result") or d.get("summary") or result.get("consensus") or ""
        # Prefer full formatted verdict if we can rebuild lightly
        tally = result.get("tally") or {}
        tally_s = ", ".join(f"{k}={v}" for k, v in tally.items())
        actions = d.get("actions") or []
        lines = [header, f"Tally: {tally_s}", ""]
        if actions:
            lines.append("Plan:")
            for i, a in enumerate(actions[:8], 1):
                lines.append(f"  {i}. {a}")
            lines.append("")
        if body:
            lines.append(str(body)[:3500])
        return "\n".join(lines)

    def list_tools(self) -> List[dict]:
        return registry.list_specs()
