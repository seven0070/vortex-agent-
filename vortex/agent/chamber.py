"""Council Chamber — real multi-agent execution after the vote.

After deliberation, selected seats become *workers*: each runs a scoped
AIAgent with its own toolset against a focused sub-goal. Results land in
the workspace chamber folder and are merged into the final verdict.

This is the "we have the resources to build" layer:
  deliberate (opinions) → dispatch (parallel seat agents) → merge (chief)
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from vortex.constants import WORKSPACE, ensure_home


# Seats that do useful tool work when dispatched (not pure meta/politics)
WORKER_PRIORITY = [
    "notebook",      # research
    "zero",          # computer / tools
    "grok",          # code
    "hermes",        # full stack
    "openworker",    # deliverable
    "officecli",     # docs
    "eve",           # files
    "odysseus",      # research workspace
    "kitesurf",      # web/edge
    "dspy",          # modular code
    "openwork",      # cowork tasks
    "tencent_memory",# memory assets
    "cognee",        # graph memory
    "multica",       # dispatch-style decompose (files)
    "ruflo",         # meta swarm (files + memory)
    "lifeos",        # plan artifact
    "opik",          # eval note
    "agent_office",  # office log
    "ai_office",     # status board
    "alook",         # room status
    "prime",         # quality criteria file
    "claw3d",        # sim notes when relevant
]

# Max parallel seat workers per council run
DEFAULT_MAX_WORKERS = 6
DEFAULT_STEPS_PER_WORKER = 6


@dataclass
class WorkAssignment:
    seat_id: str
    seat_name: str
    project: str
    toolset: str
    sub_goal: str
    icon: str = "◆"


@dataclass
class WorkResult:
    seat_id: str
    seat_name: str
    project: str
    status: str
    mission_id: str = ""
    result: str = ""
    error: str = ""
    steps: int = 0
    artifact: str = ""
    sub_goal: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:48] or "chamber")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CouncilChamber:
    """
    Dispatch parallel seat workers and merge their artifacts.

    executor_factory(toolset, role, blocked) -> AIAgent
    """

    def __init__(
        self,
        executor_factory: Callable[..., Any],
        event_cb: Optional[Callable[[dict], None]] = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
        steps_per_worker: int = DEFAULT_STEPS_PER_WORKER,
    ):
        ensure_home()
        self.executor_factory = executor_factory
        self.event_cb = event_cb
        self.max_workers = max(1, min(int(max_workers or DEFAULT_MAX_WORKERS), 12))
        self.steps_per_worker = max(2, min(int(steps_per_worker or DEFAULT_STEPS_PER_WORKER), 12))

    def _emit(self, kind: str, council_id: str, **payload):
        if not self.event_cb:
            return
        try:
            self.event_cb(
                {
                    "type": kind,
                    "ts": _now(),
                    "mission_id": council_id,
                    "session_id": council_id,
                    "council_id": council_id,
                    **payload,
                }
            )
        except Exception:
            pass

    def chamber_dir(self, council_id: str) -> Path:
        d = WORKSPACE / "council" / council_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "seats").mkdir(exist_ok=True)
        return d

    def plan_assignments(
        self,
        goal: str,
        seats: Dict[str, Any],
        seat_ids: List[str],
        directive: dict,
    ) -> List[WorkAssignment]:
        """Pick a focused set of seat workers and write concrete sub-goals."""
        g = (goal or "").lower()
        actions = list((directive or {}).get("actions") or [])

        # Domain signals → preferred seats
        want: List[str] = []
        if any(k in g for k in ("research", "report", "analyze", "investigate", "what is", "explain")):
            want += ["notebook", "odysseus", "kitesurf", "cognee", "eve"]
        if any(k in g for k in ("code", "build", "script", "implement", "benchmark", "fib", "calculate", "compute")):
            want += ["grok", "dspy", "zero", "hermes"]
        if any(k in g for k in ("memory", "remember", "recall", "knowledge", "graph")):
            want += ["tencent_memory", "cognee", "hermes"]
        if any(k in g for k in ("office", "doc", "spreadsheet", "slide", "deliverable", "write")):
            want += ["officecli", "openworker", "openwork", "eve"]
        if any(k in g for k in ("swarm", "multi-agent", "dispatch", "delegate", "team", "office")):
            want += ["ruflo", "multica", "agent_office", "ai_office", "alook"]
        if any(k in g for k in ("3d", "sim", "game", "scene")):
            want += ["claw3d", "grok"]
        if any(k in g for k in ("eval", "trace", "observ", "metric")):
            want += ["opik", "prime", "dspy"]
        if any(k in g for k in ("life", "ideal", "habit", "goal")):
            want += ["lifeos", "openworker"]
        if any(k in g for k in ("secure", "hide", "steg", "secret", "risk")):
            want += ["zero", "hermes", "prime"]

        # Always include a synthesizer + quality when building multi-domain
        if len(want) >= 2:
            want += ["openworker", "prime", "opik"]

        # Fallback: top priority seats present
        if not want:
            want = ["hermes", "zero", "notebook", "openworker", "eve", "prime"]

        # Preserve priority order, unique, only seated
        ordered: List[str] = []
        for sid in WORKER_PRIORITY:
            if sid in want and sid in seat_ids and sid in seats and sid not in ordered:
                ordered.append(sid)
        for sid in want:
            if sid in seat_ids and sid in seats and sid not in ordered:
                ordered.append(sid)

        # Cap workers
        ordered = ordered[: self.max_workers]
        if not ordered:
            ordered = [s for s in seat_ids if s in seats][:3]

        assignments: List[WorkAssignment] = []
        for sid in ordered:
            seat = seats[sid]
            sub = self._sub_goal(goal, seat, actions)
            assignments.append(
                WorkAssignment(
                    seat_id=sid,
                    seat_name=getattr(seat, "name", sid),
                    project=getattr(seat, "project", ""),
                    toolset=getattr(seat, "toolset", "core") or "core",
                    sub_goal=sub,
                    icon=getattr(seat, "icon", "◆"),
                )
            )
        return assignments

    def _sub_goal(self, goal: str, seat: Any, actions: List[str]) -> str:
        sid = getattr(seat, "id", "")
        name = getattr(seat, "name", sid)
        g = goal.strip()
        act_hint = ""
        if actions:
            # pick up to 3 actions that look tool-like
            useful = [
                a for a in actions
                if any(
                    k in a.lower()
                    for k in (
                        "search", "write", "code", "calc", "memory", "fetch",
                        "terminal", "report", "delegate", "verify", "file",
                    )
                )
            ][:3]
            if useful:
                act_hint = " Prefer steps: " + "; ".join(useful) + "."

        templates = {
            "notebook": f"Research and evidence pack for: {g}. Use web_search, then write_file reports/ with findings.",
            "odysseus": f"Local research workspace notes for: {g}. Search if needed, write_file reports/, memory_store summary.",
            "kitesurf": f"Network/edge brief for: {g}. web_search + optional http_fetch; write_file a concise report.",
            "grok": f"Technical/code path for: {g}. Use calculator or execute_code; print results; write_file code notes if useful.",
            "dspy": f"Modular program approach for: {g}. Decompose steps, run tools/code, score result, write_file modules plan.",
            "zero": f"Computer-agent execution for: {g}. Use terminal/code/search tools as needed; leave workspace artifacts.",
            "hermes": f"Full-stack agent run for: {g}. Tools + memory_store key findings; keep it lean and verified.",
            "openworker": f"Finished deliverable for: {g}. Produce a concrete workspace file the user can open.",
            "openwork": f"Workplace task completion for: {g}. Execute tools and return a finished path.",
            "officecli": f"Document deliverable for: {g}. write_file a structured markdown/csv office-style artifact.",
            "eve": f"Filesystem-first plan+artifact for: {g}. write_file plans/ and any result files; list_files to confirm.",
            "tencent_memory": f"Team memory assets for: {g}. memory_store structured findings; note reusable skill fragments.",
            "cognee": f"Knowledge-graph notes for: {g}. memory_store entity-rich text; write_file knowledge/ summary with links.",
            "multica": f"Issue dispatch plan for: {g}. Decompose into tasks; write_file issues board; suggest specialist owners.",
            "ruflo": f"Meta-harness workflow for: {g}. write_file workflow plan with parallel streams + verify/merge checklist.",
            "lifeos": f"Current→Ideal State hill-climb for: {g}. write_file plans/lifeos with current, ideal, next step.",
            "opik": f"Eval/trace rubric for: {g}. write_file eval criteria and how to score the final artifact.",
            "prime": f"Quality gate for: {g}. write_file done-criteria + verify checklist the chief must satisfy.",
            "agent_office": f"Office staffing log for: {g}. write_file roles, owners, and task board.",
            "ai_office": f"Meeting/status board for: {g}. write_file agenda + owner board.",
            "alook": f"Shared room status for: {g}. write_file a human-readable status note anyone can join mid-flight.",
            "claw3d": f"Spatial/sim notes for: {g}. If relevant write_file sim plan; else brief N/A scaffold.",
            "buzz": f"Audit trail for: {g}. write_file event-style log of decisions and approval points.",
            "qm": f"Scoped work plan for: {g}. write_file personal vs shared outputs and skill pack notes.",
        }
        base = templates.get(sid, f"As {name}, contribute a concrete workspace artifact advancing: {g}.")
        return base + act_hint + " Stay inside the Vortex workspace. Be concise."

    def run(
        self,
        council_id: str,
        goal: str,
        seats: Dict[str, Any],
        seat_ids: List[str],
        directive: dict,
        chief_factory: Optional[Callable[[], Any]] = None,
    ) -> dict:
        """
        Dispatch seat workers in parallel, then optional chief merge mission.
        Returns execution dict for CouncilSession.execution.
        """
        cdir = self.chamber_dir(council_id)
        assignments = self.plan_assignments(goal, seats, seat_ids, directive)

        # Write chamber manifesto
        manifesto = {
            "council_id": council_id,
            "goal": goal,
            "decision": (directive or {}).get("decision"),
            "assignments": [asdict(a) for a in assignments],
            "created_at": _now(),
        }
        (cdir / "manifesto.json").write_text(json.dumps(manifesto, indent=2), encoding="utf-8")
        (cdir / "README.md").write_text(
            self._readme(goal, assignments, directive),
            encoding="utf-8",
        )

        self._emit(
            "chamber_dispatch",
            council_id,
            message=f"Dispatching {len(assignments)} seat workers",
            workers=[{"seat": a.seat_id, "name": a.seat_name, "toolset": a.toolset} for a in assignments],
        )
        self._emit(
            "thought",
            council_id,
            step=10,
            thought=f"Chamber: {len(assignments)} seat agents running in parallel",
            action="chamber_dispatch",
            args={"workers": [a.seat_id for a in assignments]},
        )

        results: List[WorkResult] = []
        lock = threading.Lock()

        def run_one(asg: WorkAssignment) -> WorkResult:
            self._emit(
                "chamber_worker_start",
                council_id,
                seat=asg.seat_id,
                seat_name=asg.seat_name,
                project=asg.project,
                sub_goal=asg.sub_goal[:200],
            )
            self._emit(
                "tool_call",
                council_id,
                step=11,
                tool=f"seat:{asg.seat_id}",
                args={"sub_goal": asg.sub_goal[:180], "toolset": asg.toolset},
            )
            try:
                # Seat workers must not re-enter council
                agent = self.executor_factory(
                    toolset=asg.toolset,
                    role=f"seat:{asg.seat_id}",
                    blocked={"convene_council", "delegate_task"},
                )
                # Prefix goal so artifacts are namespaced
                mission_goal = (
                    f"[chamber:{council_id}/seat:{asg.seat_id}] {asg.sub_goal}"
                )
                result = agent.run(
                    mission_goal,
                    background=False,
                    max_steps=self.steps_per_worker,
                )
                body = result.get("result") or result.get("error") or ""
                art = cdir / "seats" / f"{asg.seat_id}.md"
                art.write_text(
                    f"# {asg.icon} {asg.seat_name} — {asg.project}\n\n"
                    f"**Sub-goal:** {asg.sub_goal}\n\n"
                    f"**Status:** {result.get('status')} · mission `{result.get('id')}` · "
                    f"{result.get('step_count', 0)} steps\n\n"
                    f"## Output\n\n{body}\n",
                    encoding="utf-8",
                )
                wr = WorkResult(
                    seat_id=asg.seat_id,
                    seat_name=asg.seat_name,
                    project=asg.project,
                    status=result.get("status") or "unknown",
                    mission_id=result.get("id") or "",
                    result=str(body)[:4000],
                    steps=int(result.get("step_count") or 0),
                    artifact=str(art.relative_to(WORKSPACE)),
                    sub_goal=asg.sub_goal,
                )
            except Exception as e:
                wr = WorkResult(
                    seat_id=asg.seat_id,
                    seat_name=asg.seat_name,
                    project=asg.project,
                    status="failed",
                    error=str(e),
                    sub_goal=asg.sub_goal,
                )
            self._emit(
                "chamber_worker_done",
                council_id,
                seat=wr.seat_id,
                seat_name=wr.seat_name,
                status=wr.status,
                steps=wr.steps,
                artifact=wr.artifact,
            )
            self._emit(
                "observation",
                council_id,
                step=11,
                tool=f"seat:{wr.seat_id}",
                status="success" if wr.status == "completed" else "error",
                observation=(
                    f"OK — {wr.seat_name}: {wr.status} · {wr.steps} steps · {wr.artifact}"
                    if wr.status == "completed"
                    else f"ERROR — {wr.seat_name}: {wr.error or wr.status}"
                ),
            )
            with lock:
                results.append(wr)
            return wr

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.max_workers, len(assignments) or 1)
        ) as pool:
            list(pool.map(run_one, assignments))

        # stable order by assignment
        order = {a.seat_id: i for i, a in enumerate(assignments)}
        results.sort(key=lambda r: order.get(r.seat_id, 99))

        (cdir / "results.json").write_text(
            json.dumps([r.to_dict() for r in results], indent=2),
            encoding="utf-8",
        )

        # Chief merge pass
        merge_body = self._merge_markdown(goal, directive, results, cdir)
        merge_path = cdir / "VERDICT.md"
        merge_path.write_text(merge_body, encoding="utf-8")

        chief_result = ""
        chief_mission = ""
        if chief_factory is not None:
            self._emit(
                "chamber_merge",
                council_id,
                message="Chief merging chamber outputs",
            )
            try:
                chief = chief_factory()
                merge_goal = (
                    f"Merge the council chamber outputs for goal: {goal}. "
                    f"Read workspace files under council/{council_id}/ if needed. "
                    f"Write a final polished summary to council/{council_id}/FINAL.md "
                    f"and memory_store a short takeaway. "
                    f"Worker artifacts: " + ", ".join(
                        r.artifact for r in results if r.artifact
                    )
                )
                # Prefer direct write of FINAL from merge_body + optional chief polish
                cr = chief.run(merge_goal, background=False, max_steps=8)
                chief_result = cr.get("result") or ""
                chief_mission = cr.get("id") or ""
            except Exception as e:
                chief_result = f"Chief merge error: {e}"

        # Always ensure FINAL.md exists
        final_path = cdir / "FINAL.md"
        if not final_path.exists():
            final_path.write_text(merge_body, encoding="utf-8")
        elif chief_result and len(chief_result) > 80:
            # append chief polish
            prev = final_path.read_text(encoding="utf-8", errors="replace")
            if chief_result[:200] not in prev:
                final_path.write_text(
                    prev + "\n\n## Chief polish\n\n" + chief_result[:4000] + "\n",
                    encoding="utf-8",
                )

        completed = sum(1 for r in results if r.status == "completed")
        failed = sum(1 for r in results if r.status not in ("completed",))
        status = "completed" if completed else "failed"

        summary = (
            f"Chamber dispatched {len(results)} seat agents "
            f"({completed} ok, {failed} failed). "
            f"Artifacts: council/{council_id}/"
        )

        return {
            "status": status,
            "mode": "chamber",
            "goal": goal,
            "workers": [r.to_dict() for r in results],
            "worker_count": len(results),
            "completed": completed,
            "failed": failed,
            "chamber_dir": str(cdir.relative_to(WORKSPACE)),
            "verdict_path": str(merge_path.relative_to(WORKSPACE)),
            "final_path": str(final_path.relative_to(WORKSPACE)),
            "chief_mission_id": chief_mission,
            "result": final_path.read_text(encoding="utf-8", errors="replace")[:6000],
            "summary": summary,
        }

    def _readme(self, goal: str, assignments: List[WorkAssignment], directive: dict) -> str:
        lines = [
            f"# Council Chamber",
            f"",
            f"**Goal:** {goal}",
            f"**Decision:** {(directive or {}).get('decision', '?')}",
            f"**Created:** {_now()}",
            f"",
            f"## Workers",
        ]
        for a in assignments:
            lines.append(
                f"- {a.icon} **{a.seat_name}** (`{a.seat_id}`) · toolset `{a.toolset}`  "
                f"  \n  {a.sub_goal[:160]}"
            )
        lines += ["", "## Layout", "- `seats/<id>.md` — per-seat agent output", "- `VERDICT.md` — merged verdict", "- `FINAL.md` — chief-polished final", "- `manifesto.json` / `results.json` — machine-readable"]
        return "\n".join(lines) + "\n"

    def _merge_markdown(
        self,
        goal: str,
        directive: dict,
        results: List[WorkResult],
        cdir: Path,
    ) -> str:
        d = directive or {}
        lines = [
            "# ⚖ Chamber Verdict — Multi-Agent Execution",
            f"**Goal:** {goal}",
            f"**Council decision:** {(d.get('decision') or '?').upper()}",
            f"**Tally:** " + ", ".join(f"{k}={v}" for k, v in (d.get("tally") or {}).items()),
            f"**Generated:** {_now()}",
            "",
            "## Consensus plan",
            d.get("summary") or "—",
            "",
        ]
        if d.get("actions"):
            lines.append("### Actions")
            for i, a in enumerate(d["actions"][:12], 1):
                lines.append(f"{i}. {a}")
            lines.append("")
        if d.get("risks"):
            lines.append("### Risks")
            for r in d["risks"][:8]:
                lines.append(f"- ⚠ {r}")
            lines.append("")

        lines += ["## Seat worker results", ""]
        for r in results:
            flag = "✅" if r.status == "completed" else "❌"
            lines.append(
                f"### {flag} {r.seat_name} (`{r.seat_id}`)"
            )
            lines.append(f"- project: `{r.project}`")
            lines.append(f"- status: **{r.status}** · steps: {r.steps} · mission: `{r.mission_id}`")
            if r.artifact:
                lines.append(f"- artifact: `{r.artifact}`")
            if r.error:
                lines.append(f"- error: {r.error}")
            body = (r.result or "").strip()
            if body:
                # keep each seat contribution bounded
                lines.append("")
                lines.append(body[:1200])
                if len(body) > 1200:
                    lines.append("…")
            lines.append("")

        lines += [
            "## Artifacts",
            f"- Chamber: `{cdir.relative_to(WORKSPACE)}/`",
            f"- Final: `{cdir.relative_to(WORKSPACE)}/FINAL.md`",
            "",
            "_Built by Vortex Council Chamber — parallel seat agents under the autonomous chief._",
            "",
        ]
        return "\n".join(lines)
