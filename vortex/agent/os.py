"""VortexOS — owns sessions, swarm bots, skills, memory, autonomy (the waist)."""
from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional

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
        )
        # short goals for specialists — run as mission
        result = agent.run(message, background=False)
        return result.get("result") or result.get("error") or "(empty)"


class VortexOS:
    """
    The OS layer:
      - shared SessionDB / vector / skills / memory
      - swarm of role bots
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

        # primary autonomous agent (full toolset)
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
        )
        # alias used by API layer
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

    # ── event bus ──────────────────────────────────────────────────────────
    def subscribe(self, cb: Callable[[dict], None]):
        self._listeners.append(cb)
        # also wire primary agent
        self.agent.event_cb = self._fanout

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

    # ── chat / missions ────────────────────────────────────────────────────
    def chat(self, message: str) -> str:
        self.db.add_message("main", "user", message)
        # direct @bot
        if message.startswith("@"):
            name, _, rest = message[1:].partition(" ")
            if name in self.bots:
                reply = self.bots[name].handle(rest)
                self.db.add_message("main", f"bot:{name}", reply)
                return reply
            return f"Unknown bot '{name}'. Active: {', '.join(self.bots)}"

        # chief handles (may auto-run mission)
        if "chief" in self.bots and not message.lower().startswith("/auto"):
            # Use primary agent chat for consistency
            reply = self.agent.chat(message)
        else:
            reply = self.agent.chat(message)
        self.db.add_message("main", "assistant", reply)
        return reply

    def list_tools(self) -> List[dict]:
        return registry.list_specs()
