"""Autonomous agent — goal-driven plan → act → observe loop."""
from __future__ import annotations

import json
import re
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from llm import LLMBrain, parse_action
from tools import build_toolbelt, run_tool, tools_description, ToolResult, WORKSPACE


EventCallback = Callable[[dict], None]


@dataclass
class StepRecord:
    index: int
    thought: str
    action: str
    args: dict
    observation: str
    status: str
    ts: str


@dataclass
class Mission:
    id: str
    goal: str
    status: str = "queued"  # queued|running|completed|failed|cancelled
    max_steps: int = 12
    steps: List[StepRecord] = field(default_factory=list)
    result: str = ""
    error: str = ""
    created_at: str = ""
    finished_at: str = ""
    provider: str = "offline"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status,
            "max_steps": self.max_steps,
            "steps": [asdict(s) for s in self.steps],
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "provider": self.provider,
            "step_count": len(self.steps),
        }


class AutonomousAgent:
    """
    Owns missions and runs the ReAct loop in background threads.
    Emits structured events for SSE / websocket consumers.
    """

    def __init__(self, memory, vector, skills=None, bugs=None):
        self.memory = memory
        self.vector = vector
        self.skills = skills
        self.bugs = bugs
        self.brain = LLMBrain()
        self.tools = build_toolbelt(vector=vector, memory=memory)
        self.missions: Dict[str, Mission] = {}
        self._lock = threading.Lock()
        self._listeners: List[EventCallback] = []
        self._cancel = set()
        # last search results for http_fetch from_search convenience
        self._last_search_results: List[dict] = []
        self._last_research_blob: str = ""

    # ── event bus ──────────────────────────────────────────────────────────
    def subscribe(self, cb: EventCallback):
        self._listeners.append(cb)

    def unsubscribe(self, cb: EventCallback):
        if cb in self._listeners:
            self._listeners.remove(cb)

    def _emit(self, kind: str, payload: dict):
        event = {
            "type": kind,
            "ts": datetime.now().isoformat(timespec="seconds"),
            **payload,
        }
        for cb in list(self._listeners):
            try:
                cb(event)
            except Exception:
                pass
        try:
            self.memory.log_event(kind, json.dumps(payload)[:500])
        except Exception:
            pass

    # ── public API ─────────────────────────────────────────────────────────
    def list_tools(self) -> List[dict]:
        out = []
        for name, t in self.tools.items():
            out.append(
                {
                    "name": name,
                    "description": getattr(t, "description", ""),
                    "parameters": getattr(t, "parameters", {}),
                }
            )
        return out

    def list_missions(self) -> List[dict]:
        with self._lock:
            return [m.to_dict() for m in sorted(
                self.missions.values(), key=lambda x: x.created_at, reverse=True
            )]

    def get_mission(self, mid: str) -> Optional[dict]:
        m = self.missions.get(mid)
        return m.to_dict() if m else None

    def cancel(self, mid: str) -> bool:
        if mid in self.missions and self.missions[mid].status == "running":
            self._cancel.add(mid)
            return True
        return False

    def start_mission(self, goal: str, max_steps: int = 12, background: bool = True) -> dict:
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("goal required")
        mid = uuid.uuid4().hex[:12]
        mission = Mission(
            id=mid,
            goal=goal,
            status="queued",
            max_steps=max(1, min(int(max_steps or 12), 25)),
            created_at=datetime.now().isoformat(timespec="seconds"),
            provider=self.brain.provider,
        )
        with self._lock:
            self.missions[mid] = mission
        self.memory.save_message("user", f"[mission:{mid}] {goal}")
        self._emit("mission_queued", {"mission_id": mid, "goal": goal})

        if background:
            t = threading.Thread(target=self._run, args=(mid,), daemon=True)
            t.start()
        else:
            self._run(mid)
        return mission.to_dict()

    def run_sync(self, goal: str, max_steps: int = 12) -> dict:
        return self.start_mission(goal, max_steps=max_steps, background=False)

    # ── core loop ──────────────────────────────────────────────────────────
    def _run(self, mid: str):
        mission = self.missions[mid]
        mission.status = "running"
        self._emit("mission_started", {"mission_id": mid, "goal": mission.goal})

        # reset per-mission research cache
        self._last_search_results = []
        self._last_research_blob = ""
        self._current_goal = mission.goal

        desc = tools_description(self.tools)
        messages: List[Dict[str, str]] = [
            {
                "role": "user",
                "content": (
                    f"GOAL: {mission.goal}\n"
                    f"Workspace: {WORKSPACE}\n"
                    f"Complete this goal autonomously using tools. "
                    f"You have at most {mission.max_steps} steps."
                ),
            }
        ]

        try:
            for i in range(mission.max_steps):
                if mid in self._cancel:
                    mission.status = "cancelled"
                    mission.finished_at = datetime.now().isoformat(timespec="seconds")
                    self._emit("mission_cancelled", {"mission_id": mid})
                    self._cancel.discard(mid)
                    return

                self._emit(
                    "thinking",
                    {"mission_id": mid, "step": i + 1, "message": "Planning next action…"},
                )

                raw = self.brain.chat(messages, tools_desc=desc)
                action = parse_action(raw)
                thought = action.get("thought") or ""
                name = (action.get("action") or "finish").strip()
                args = action.get("args") or {}

                self._emit(
                    "thought",
                    {
                        "mission_id": mid,
                        "step": i + 1,
                        "thought": thought,
                        "action": name,
                        "args": args,
                    },
                )

                if name in ("finish", "done", "final", "respond"):
                    result = (
                        args.get("result")
                        or args.get("answer")
                        or args.get("message")
                        or thought
                        or "Done."
                    )
                    # enrich finish with research if empty-ish
                    if self._last_research_blob and len(str(result)) < 80:
                        result = self._compose_report(mission.goal)
                    mission.result = str(result)
                    mission.status = "completed"
                    mission.finished_at = datetime.now().isoformat(timespec="seconds")
                    step = StepRecord(
                        index=i + 1,
                        thought=thought,
                        action="finish",
                        args=args,
                        observation=mission.result[:500],
                        status="success",
                        ts=datetime.now().isoformat(timespec="seconds"),
                    )
                    mission.steps.append(step)
                    self.memory.save_message(
                        "assistant",
                        mission.result,
                        meta={"mission_id": mid, "steps": len(mission.steps)},
                    )
                    self.vector.remember(
                        f"[mission:{mid}] {mission.goal} => {mission.result[:300]}",
                        {"mission": mid},
                    )
                    if self.skills:
                        try:
                            self.skills.save(
                                f"mission_{mid}",
                                mission.goal[:120],
                                [s.action for s in mission.steps],
                            )
                        except Exception:
                            pass
                    self._emit(
                        "mission_completed",
                        {
                            "mission_id": mid,
                            "result": mission.result,
                            "steps": len(mission.steps),
                        },
                    )
                    return

                # special arg rewriting for chained research tools
                args = self._rewrite_args(name, args)

                self._emit(
                    "tool_call",
                    {
                        "mission_id": mid,
                        "step": i + 1,
                        "tool": name,
                        "args": self._public_args(args),
                    },
                )

                result = run_tool(self.tools, name, args)
                obs = result.observation()
                self._ingest_result(name, result)

                step = StepRecord(
                    index=i + 1,
                    thought=thought,
                    action=name,
                    args=self._public_args(args),
                    observation=obs[:2000],
                    status=result.status,
                    ts=datetime.now().isoformat(timespec="seconds"),
                )
                mission.steps.append(step)

                self._emit(
                    "observation",
                    {
                        "mission_id": mid,
                        "step": i + 1,
                        "tool": name,
                        "status": result.status,
                        "observation": obs[:2000],
                        "data": result.data if result.status == "success" else {},
                    },
                )

                if result.status == "error" and self.bugs:
                    try:
                        self.bugs.add(
                            {
                                "bot": "autonomous",
                                "tool": name,
                                "symptoms": [result.message[:80]],
                                "fix": "review args / retry",
                            }
                        )
                    except Exception:
                        pass

                # feed back into the conversation
                messages.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {"thought": thought, "action": name, "args": args}
                        ),
                    }
                )
                messages.append({"role": "user", "content": f"Observation: {obs}"})

                # small pacing so SSE clients can breathe
                time.sleep(0.05)

            # max steps exhausted — synthesize best answer
            mission.result = self._compose_report(mission.goal) if self._last_research_blob else (
                "Reached max steps. Partial progress:\n"
                + "\n".join(
                    f"{s.index}. {s.action} → {s.status}: {s.observation[:200]}"
                    for s in mission.steps
                )
            )
            mission.status = "completed"
            mission.finished_at = datetime.now().isoformat(timespec="seconds")
            self.memory.save_message(
                "assistant", mission.result, meta={"mission_id": mid, "partial": True}
            )
            self._emit(
                "mission_completed",
                {
                    "mission_id": mid,
                    "result": mission.result,
                    "steps": len(mission.steps),
                    "partial": True,
                },
            )
        except Exception as e:
            mission.status = "failed"
            mission.error = f"{e}\n{traceback.format_exc()[-500:]}"
            mission.finished_at = datetime.now().isoformat(timespec="seconds")
            self._emit(
                "mission_failed",
                {"mission_id": mid, "error": str(e)},
            )

    # ── helpers ────────────────────────────────────────────────────────────
    def _rewrite_args(self, name: str, args: dict) -> dict:
        args = dict(args or {})
        if name == "http_fetch" and (
            args.get("from_search") or not args.get("url")
        ):
            # pick first result with a url
            for r in self._last_search_results:
                if r.get("url"):
                    args["url"] = r["url"]
                    break
            args.pop("from_search", None)

        if name == "write_file" and args.get("from_research"):
            args["content"] = self._compose_report(
                goal=getattr(self, "_current_goal", "") or "",
            )
            args.pop("from_research", None)

        if name == "remember" and args.get("from_research"):
            args["text"] = (
                self._last_research_blob[:1500]
                or args.get("text")
                or "research complete"
            )
            args.pop("from_research", None)
            args.setdefault("tag", "research")
        return args

    def _ingest_result(self, name: str, result: ToolResult):
        if result.status != "success":
            return
        if name == "web_search":
            self._last_search_results = result.data.get("results") or []
            bits = []
            for r in self._last_search_results:
                bits.append(
                    f"- {r.get('title','')}: {r.get('snippet','')} ({r.get('url','')})"
                )
            self._last_research_blob += "\n## Search\n" + "\n".join(bits) + "\n"
        elif name == "http_fetch":
            text = (result.data.get("text") or "")[:3000]
            url = result.data.get("url") or ""
            self._last_research_blob += f"\n## Source {url}\n{text}\n"
        elif name == "codeforge":
            self._last_research_blob += (
                f"\n## Code output\n{result.data.get('output','')}\n"
            )
        elif name == "calculator":
            self._last_research_blob += (
                f"\n## Calculation\n{result.data.get('expression')} = "
                f"{result.data.get('result')}\n"
            )
        elif name == "steganography" and "encoded" in result.data:
            try:
                self.memory.set_kv("last_stego", result.data["encoded"])
            except Exception:
                pass

    def _compose_report(self, goal: str = "", seed_content: str = None) -> str:
        title = (goal or "Autonomous report").strip()
        # strip accidental markdown headers from title
        title = re.sub(r"^#+\s*", "", title).split("\n")[0][:100] or "Autonomous report"
        body = self._last_research_blob.strip() or "_No research gathered._"
        return (
            f"# {title}\n\n"
            f"_Generated by Vortex Autonomous Agent · "
            f"{datetime.now().isoformat(timespec='seconds')}_\n\n"
            f"## Goal\n{goal or title}\n\n"
            f"## Findings\n{body}\n\n"
            f"## Conclusion\n"
            f"Autonomous run finished with the findings above. "
            f"Open the workspace file for the full artifact.\n"
        )

    @staticmethod
    def _public_args(args: dict) -> dict:
        """Truncate huge arg values for events/UI."""
        out = {}
        for k, v in (args or {}).items():
            s = v if not isinstance(v, (dict, list)) else json.dumps(v)
            s = str(s)
            out[k] = s if len(s) <= 500 else s[:500] + "…"
        return out
