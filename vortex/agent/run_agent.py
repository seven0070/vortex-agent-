"""AIAgent — core conversation / mission loop (Hermes run_agent spirit)."""
from __future__ import annotations

import json
import re
import threading
import time
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from vortex.agent.llm import LLMBrain, parse_action
from vortex.agent.prompt_builder import build_system_prompt
from vortex.constants import WORKSPACE
from vortex.toolsets import resolve_many
from vortex.tools.registry import registry

# Ensure tools are registered
import vortex.tools  # noqa: F401

EventCB = Callable[[dict], None]


class AIAgent:
    """
    Synchronous orchestration engine.

    Entry points:
      - run(goal)            → autonomous mission (ReAct loop)
      - chat(message)        → single-turn / multi-turn conversation
    """

    def __init__(
        self,
        session_db=None,
        vector=None,
        skills=None,
        memory_provider=None,
        toolsets: Optional[List[str]] = None,
        max_steps: int = 12,
        event_cb: Optional[EventCB] = None,
        parent_id: Optional[str] = None,
        role: str = "agent",
        blocked_tools: Optional[Set[str]] = None,
        brain: Optional[LLMBrain] = None,
        council=None,
    ):
        from vortex.agent.state import SessionDB
        from vortex.agent.vector_memory import VectorMemory
        from vortex.agent.skills import SkillHub
        from vortex.agent.memory_provider import BuiltinMemory

        self.session_db = session_db or SessionDB()
        self.vector = vector or VectorMemory()
        self.skills = skills or SkillHub()
        self.memory_provider = memory_provider or BuiltinMemory()
        self.toolsets = toolsets or ["full"]
        self.max_steps = max(1, min(int(max_steps or 12), 30))
        self.event_cb = event_cb
        self.parent_id = parent_id
        self.role = role
        self.blocked_tools = set(blocked_tools or [])
        self.brain = brain or LLMBrain()
        self.council = council
        self.session_id: Optional[str] = None
        self._cancel = False
        self._research_blob = ""
        self._last_search: List[dict] = []
        self._todos: List[dict] = []
        # in-memory mission cache for API compat
        self._live: Dict[str, dict] = {}

    # ── tool resolution ────────────────────────────────────────────────────
    def enabled_tools(self) -> List[str]:
        names = resolve_many(self.toolsets)
        return [n for n in names if n not in self.blocked_tools and registry.get(n)]

    def tools_block(self) -> str:
        # filter description to enabled only
        lines = []
        for name in self.enabled_tools():
            t = registry.get(name)
            if not t:
                continue
            props = list((t.parameters.get("properties") or {}).keys())
            lines.append(f"- {t.name}({', '.join(props)}): {t.description}")
        return "\n".join(lines)

    # ── events ─────────────────────────────────────────────────────────────
    def _emit(self, kind: str, payload: dict):
        event = {
            "type": kind,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "mission_id": self.session_id,  # UI compat
            "session_id": self.session_id,
            **payload,
        }
        if self.event_cb:
            try:
                self.event_cb(event)
            except Exception:
                pass
        try:
            self.session_db.log_event(kind, json.dumps(payload)[:500], self.session_id or "")
        except Exception:
            pass

    # ── public API ─────────────────────────────────────────────────────────
    def run(self, goal: str, background: bool = False, max_steps: Optional[int] = None) -> dict:
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("goal required")
        if max_steps:
            self.max_steps = max(1, min(int(max_steps), 30))

        sid = self.session_db.new_session(
            goal=goal, role=self.role, parent_id=self.parent_id
        )
        self.session_id = sid
        self._cancel = False
        self._research_blob = ""
        self._last_search = []

        snapshot = {
            "id": sid,
            "goal": goal,
            "status": "queued",
            "max_steps": self.max_steps,
            "steps": [],
            "result": "",
            "error": "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": "",
            "provider": self.brain.provider,
            "step_count": 0,
        }
        self._live[sid] = snapshot
        self._emit("mission_queued", {"goal": goal})

        if background:
            t = threading.Thread(target=self._loop, args=(sid, goal), daemon=True)
            t.start()
            return dict(snapshot)

        return self._loop(sid, goal)

    def cancel(self, sid: Optional[str] = None) -> bool:
        target = sid or self.session_id
        if target and target in self._live and self._live[target]["status"] == "running":
            if target == self.session_id:
                self._cancel = True
            # best-effort flag via kv
            self.session_db.set_kv(f"cancel:{target}", "1")
            return True
        return False

    def get_mission(self, sid: str) -> Optional[dict]:
        if sid in self._live:
            # merge with db steps
            db = self.session_db.get_session(sid) or {}
            live = dict(self._live[sid])
            if db.get("steps"):
                live["steps"] = db["steps"]
                live["step_count"] = len(db["steps"])
            if db.get("result"):
                live["result"] = db["result"]
            if db.get("status"):
                live["status"] = db["status"]
            return live
        return self.session_db.get_session(sid)

    def list_missions(self) -> List[dict]:
        return self.session_db.list_sessions(50)

    def chat(self, message: str) -> str:
        """Chief-style chat: small talk or auto-launch mission."""
        low = (message or "").lower().strip()
        if not low:
            return "Say something, or give me a goal."

        if low in ("hello", "hi", "hey", "yo"):
            return (
                f"🌪️ Vortex Agent online · brain={self.brain.provider} · "
                f"tools={len(self.enabled_tools())}. "
                "Give me a goal, `/auto <goal>`, or `/council <goal>`."
            )
        if low in ("help", "/help", "who are you"):
            return (
                "I'm Vortex Agent — an autonomous multi-agent OS with a 24-seat council chamber.\n"
                "  • Describe a goal and I'll plan → act → observe\n"
                "  • `/auto <goal>` force a solo mission\n"
                "  • `/council <goal>` deliberate, vote, then chamber-execute\n"
                "  • Tools: " + ", ".join(self.enabled_tools()[:12]) + "…"
            )
        if low.startswith("/council ") or low.startswith("/deliberate "):
            goal = message.split(" ", 1)[1].strip()
            if not self.council:
                return "Council is not wired into this agent."
            result = self.council.convene(goal, auto_execute=True, background=False)
            d = result.get("directive") or {}
            ex = result.get("execution") or {}
            return (
                f"⚖ Council [{result.get('id')}] · {d.get('decision', '?').upper()}\n"
                f"{ex.get('result') or d.get('summary') or ''}"
            )[:4000]
        if low.startswith("/auto "):
            goal = message.split(" ", 1)[1].strip()
            result = self.run(goal, background=False)
            return self._format_mission(result)

        # heuristic: complex goals → mission
        triggers = (
            "research", "investigate", "build", "create", "calculate",
            "analyze", "analyse", "hide", "write a", "find out", "look up",
            "report", "system info", "benchmark", "fibonacci",
        )
        if any(t in low for t in triggers) or len(message) > 80:
            result = self.run(message, background=False)
            return self._format_mission(result)

        return (
            "🌪️ Ready. Give me a concrete goal (research / build / calculate / secure) "
            "or `/auto <goal>`."
        )

    @staticmethod
    def _format_mission(result: dict) -> str:
        status = result.get("status")
        body = result.get("result") or result.get("error") or "(no result)"
        return (
            f"🤖 Mission [{result.get('id')}] — {status} · "
            f"{result.get('step_count', 0)} steps\n\n{body}"
        )

    # ── core loop ──────────────────────────────────────────────────────────
    def _loop(self, sid: str, goal: str) -> dict:
        self.session_id = sid
        live = self._live.setdefault(
            sid,
            {
                "id": sid,
                "goal": goal,
                "status": "running",
                "steps": [],
                "result": "",
                "error": "",
                "provider": self.brain.provider,
                "step_count": 0,
                "max_steps": self.max_steps,
            },
        )
        live["status"] = "running"
        self.session_db.update_session(sid, status="running")
        self.session_db.add_message(sid, "user", goal)
        self._emit("mission_started", {"goal": goal})

        tools_block = self.tools_block()
        system = build_system_prompt(
            tools_block=tools_block,
            skills_block=self.skills.prompt_block(),
            memory_block=self.memory_provider.system_prompt_block(),
            role=self.role,
        )
        messages: List[Dict[str, str]] = [
            {
                "role": "user",
                "content": (
                    f"GOAL: {goal}\n"
                    f"Workspace: {WORKSPACE}\n"
                    f"Complete this goal autonomously using tools. "
                    f"You have at most {self.max_steps} steps."
                ),
            }
        ]

        try:
            for i in range(self.max_steps):
                if self._cancel or self.session_db.get_kv(f"cancel:{sid}") == "1":
                    live["status"] = "cancelled"
                    self.session_db.update_session(
                        sid,
                        status="cancelled",
                        finished_at=datetime.now().isoformat(timespec="seconds"),
                    )
                    self._emit("mission_cancelled", {})
                    return live

                self._emit("thinking", {"step": i + 1, "message": "Planning…"})
                raw = self.brain.chat(messages, tools_desc=tools_block, system=system)
                action = parse_action(raw)
                thought = action.get("thought") or ""
                name = (action.get("action") or "finish").strip()
                args = dict(action.get("args") or {})

                self._emit(
                    "thought",
                    {"step": i + 1, "thought": thought, "action": name, "args": self._pub(args)},
                )

                if name in ("finish", "done", "final", "respond"):
                    result = (
                        args.get("result")
                        or args.get("answer")
                        or args.get("message")
                        or thought
                        or "Done."
                    )
                    if self._research_blob and len(str(result)) < 80:
                        result = self._compose_report(goal)
                    return self._complete(sid, live, i + 1, thought, args, str(result))

                # rewrite chained research args
                args = self._rewrite(name, args, goal)

                if name not in self.enabled_tools():
                    obs = f"ERROR: Unknown or disabled tool '{name}'"
                    self._record_step(sid, live, i + 1, thought, name, args, obs, "error")
                    messages.append(
                        {"role": "assistant", "content": json.dumps({"thought": thought, "action": name, "args": args})}
                    )
                    messages.append({"role": "user", "content": f"Observation: {obs}"})
                    continue

                self._emit(
                    "tool_call",
                    {"step": i + 1, "tool": name, "args": self._pub(args)},
                )

                ctx = {
                    "agent": self,
                    "memory": self.session_db,
                    "vector": self.vector,
                    "skills": self.skills,
                    "memory_provider": self.memory_provider,
                    "council": self.council,
                    "_todos": self._todos,
                    "session_id": sid,
                }
                # strip control flags before dispatch
                call_args = {
                    k: v
                    for k, v in args.items()
                    if k not in ("from_research",)
                }
                result = registry.dispatch(name, call_args, context=ctx)
                obs = registry.observation(result)
                self._ingest(name, result)

                self._record_step(
                    sid, live, i + 1, thought, name, args, obs, result.get("status", "error")
                )
                self._emit(
                    "observation",
                    {
                        "step": i + 1,
                        "tool": name,
                        "status": result.get("status"),
                        "observation": obs[:2000],
                        "data": result.get("data") if result.get("status") == "success" else {},
                    },
                )

                messages.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {"thought": thought, "action": name, "args": call_args}
                        ),
                    }
                )
                messages.append({"role": "user", "content": f"Observation: {obs}"})
                time.sleep(0.02)

            # max steps
            result = (
                self._compose_report(goal)
                if self._research_blob
                else "Reached max steps.\n"
                + "\n".join(
                    f"{s['index']}. {s['action']} → {s['status']}"
                    for s in live.get("steps", [])
                )
            )
            return self._complete(sid, live, self.max_steps, "max steps", {}, result, partial=True)

        except Exception as e:
            live["status"] = "failed"
            live["error"] = f"{e}"
            live["finished_at"] = datetime.now().isoformat(timespec="seconds")
            self.session_db.update_session(
                sid,
                status="failed",
                error=str(e)[:500],
                finished_at=live["finished_at"],
            )
            self._emit("mission_failed", {"error": str(e)})
            return live

    def _complete(self, sid, live, idx, thought, args, result, partial=False):
        now = datetime.now().isoformat(timespec="seconds")
        live["result"] = result
        live["status"] = "completed"
        live["finished_at"] = now
        live["step_count"] = len(live.get("steps") or []) + (
            0 if any(s.get("action") == "finish" for s in live.get("steps") or []) else 1
        )
        self.session_db.add_step(sid, idx, thought, "finish", args, result[:500], "success")
        live.setdefault("steps", []).append(
            {
                "index": idx,
                "thought": thought,
                "action": "finish",
                "args": args,
                "observation": result[:500],
                "status": "success",
                "ts": now,
            }
        )
        live["step_count"] = len(live["steps"])
        self.session_db.update_session(
            sid, status="completed", result=result, finished_at=now
        )
        self.session_db.add_message(sid, "assistant", result, {"partial": partial})
        try:
            self.vector.remember(f"[mission:{sid}] {live.get('goal')} => {result[:300]}", {"mission": sid})
        except Exception:
            pass
        try:
            steps = [s["action"] for s in live["steps"]]
            self.skills.save_learned(f"mission_{sid}", (live.get("goal") or "")[:120], steps)
        except Exception:
            pass
        self._emit(
            "mission_completed",
            {"result": result, "steps": live["step_count"], "partial": partial},
        )
        return live

    def _record_step(self, sid, live, idx, thought, action, args, obs, status):
        now = datetime.now().isoformat(timespec="seconds")
        step = {
            "index": idx,
            "thought": thought,
            "action": action,
            "args": self._pub(args),
            "observation": obs[:2000],
            "status": status,
            "ts": now,
        }
        live.setdefault("steps", []).append(step)
        live["step_count"] = len(live["steps"])
        self.session_db.add_step(
            sid, idx, thought, action, self._pub(args), obs[:2000], status
        )

    def _rewrite(self, name: str, args: dict, goal: str) -> dict:
        args = dict(args or {})
        if name == "http_fetch" and (args.get("from_search") or not args.get("url")):
            for r in self._last_search:
                if r.get("url"):
                    args["url"] = r["url"]
                    break
            args.pop("from_search", None)
        if name == "write_file" and args.get("from_research"):
            args["content"] = self._compose_report(goal)
            args.pop("from_research", None)
        if name == "memory_store" and args.get("from_research"):
            args["text"] = self._research_blob[:1500] or args.get("text") or "research complete"
            args.pop("from_research", None)
            args.setdefault("tag", "research")
        return args

    def _ingest(self, name: str, result: dict):
        if result.get("status") != "success":
            return
        data = result.get("data") or {}
        if name == "web_search":
            self._last_search = data.get("results") or []
            bits = [
                f"- {r.get('title','')}: {r.get('snippet','')} ({r.get('url','')})"
                for r in self._last_search
            ]
            self._research_blob += "\n## Search\n" + "\n".join(bits) + "\n"
        elif name == "http_fetch":
            self._research_blob += (
                f"\n## Source {data.get('url','')}\n{(data.get('text') or '')[:3000]}\n"
            )
        elif name == "execute_code":
            self._research_blob += f"\n## Code output\n{data.get('output','')}\n"
        elif name == "calculator":
            self._research_blob += (
                f"\n## Calculation\n{data.get('expression')} = {data.get('result')}\n"
            )

    def _compose_report(self, goal: str = "") -> str:
        title = re.sub(r"^#+\s*", "", (goal or "Autonomous report")).split("\n")[0][:100]
        body = self._research_blob.strip() or "_No research gathered._"
        return (
            f"# {title}\n\n"
            f"_Generated by Vortex · {datetime.now().isoformat(timespec='seconds')}_\n\n"
            f"## Goal\n{goal}\n\n"
            f"## Findings\n{body}\n\n"
            f"## Conclusion\nAutonomous run finished. See workspace for artifacts.\n"
        )

    @staticmethod
    def _pub(args: dict) -> dict:
        out = {}
        for k, v in (args or {}).items():
            s = v if not isinstance(v, (dict, list)) else json.dumps(v)
            s = str(s)
            out[k] = s if len(s) <= 500 else s[:500] + "…"
        return out
