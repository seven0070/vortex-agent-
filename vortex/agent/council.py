"""AI Agent Council — multi-project deliberation under the autonomous chief.

Each seat is inspired by a real open-source agent project. They brief,
propose, critique, and vote; Vortex's autonomous chief executes the
consensus directive.

Seats (council members):
  ♟  Agent Prime   — Avyayalaya/agent-prime      quality gate · persistent OS
  🖥  Agent Zero    — agent0ai/agent-zero         full computer · autonomy
  🐝  Buzz          — block/buzz                  hive mind · human↔agent rooms
  ☤  Hermes        — NousResearch/hermes-agent   learning loop · skills · memory
  🏢  QM            — yc-software/qm              multiplayer work harness
  📁  Eve           — vercel/eve                  filesystem-first durable agents
  🗺  Odysseus      — odysseus-dev/odysseus       self-hosted AI workspace
  👷  OpenWorker    — andrewyng/openworker        finished deliverables
  ⚡  Grok Build    — xai-org/grok-build          coding harness · TUI · shell
  📓  Notebook      — research synthesizer        evidence · structured notes
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from vortex.agent.llm import LLMBrain


EventCB = Callable[[dict], None]


# ── Personas (= council member projects) ────────────────────────────────────

@dataclass
class Seat:
    """One chair at the council table — mapped to a real agent project."""
    id: str
    name: str
    title: str
    project: str                 # org/repo
    url: str
    mandate: str
    lens: str
    toolset: str
    weight: float = 1.0
    color: str = "#f97316"
    icon: str = "◆"

    def system_block(self) -> str:
        return (
            f"You are {self.name} ({self.title}), seated on the Vortex Agent Council.\n"
            f"You embody the philosophy of {self.project} — {self.url}\n"
            f"Mandate: {self.mandate}\n"
            f"Lens: {self.lens}\n"
            f"Be pointed, concrete, and brief. No fluff. Stay in character."
        )


DEFAULT_SEATS: List[Seat] = [
    Seat(
        id="prime",
        name="Prime",
        title="Quality Gate & Persistent OS",
        project="Avyayalaya/agent-prime",
        url="https://github.com/Avyayalaya/agent-prime",
        mandate=(
            "Enforce standards, quality gates, and persistent memory of decisions. "
            "Reject thin plans; demand recursive improvement and durable rules."
        ),
        lens="Markdown-first OS — every correction becomes a permanent rule.",
        toolset="full",
        weight=1.4,
        color="#a78bfa",
        icon="♟",
    ),
    Seat(
        id="zero",
        name="Zero",
        title="Full-Computer Autonomy",
        project="agent0ai/agent-zero",
        url="https://github.com/agent0ai/agent-zero",
        mandate=(
            "Give the agent a real computer: shell, browser, files, desktop apps. "
            "Push for concrete tool use, host bridges, and multi-agent delegation."
        ),
        lens="Not chat — a full Linux machine the agent actually drives.",
        toolset="full",
        weight=1.3,
        color="#22d3ee",
        icon="🖥",
    ),
    Seat(
        id="buzz",
        name="Buzz",
        title="Hive Mind & Collaboration",
        project="block/buzz",
        url="https://github.com/block/buzz",
        mandate=(
            "Design human↔agent rooms, signed event logs, shared channels. "
            "Ensure work is auditable and multiplayer, not a black box."
        ),
        lens="People and agents in the same room — one relay, one audit trail.",
        toolset="core",
        weight=1.1,
        color="#fbbf24",
        icon="🐝",
    ),
    Seat(
        id="hermes",
        name="Hermes",
        title="Self-Improving Agent Core",
        project="NousResearch/hermes-agent",
        url="https://github.com/NousResearch/hermes-agent",
        mandate=(
            "Own the learning loop: skills from experience, memory, subagents, "
            "narrow core waist with capability at the edges."
        ),
        lens="The agent that grows with you — skills, memory, cron, gateway.",
        toolset="full",
        weight=1.5,
        color="#f97316",
        icon="☤",
    ),
    Seat(
        id="qm",
        name="QM",
        title="Multiplayer Work Harness",
        project="yc-software/qm",
        url="https://github.com/yc-software/qm",
        mandate=(
            "Scope work for teams: personal + shared memory, skills packs, "
            "crons, permissions, org-ready harness switching."
        ),
        lens="Agents for startups — isolated workspaces that still collaborate.",
        toolset="core",
        weight=1.2,
        color="#34d399",
        icon="🏢",
    ),
    Seat(
        id="eve",
        name="Eve",
        title="Filesystem-First Framework",
        project="vercel/eve",
        url="https://github.com/vercel/eve",
        mandate=(
            "Keep agents durable and inspectable: instructions.md, tools/, skills/, "
            "schedules/ as the authoring interface. Prefer files over hidden state."
        ),
        lens="The filesystem is the API — markdown and typed tools you can git.",
        toolset="files",
        weight=1.2,
        color="#60a5fa",
        icon="📁",
    ),
    Seat(
        id="odysseus",
        name="Odysseus",
        title="Self-Hosted AI Workspace",
        project="odysseus-dev/odysseus",
        url="https://github.com/odysseus-dev/odysseus",
        mandate=(
            "Own the local workspace: chat, docs, notes, research, calendar, "
            "local models. Prefer self-hosted, private, all-in-one surfaces."
        ),
        lens="Your data stays home — research + documents + agents in one place.",
        toolset="research",
        weight=1.1,
        color="#c084fc",
        icon="🗺",
    ),
    Seat(
        id="openworker",
        name="OpenWorker",
        title="Finished-Work Coworker",
        project="andrewyng/openworker",
        url="https://github.com/andrewyng/openworker",
        mandate=(
            "Deliver finished artifacts, not chat. Break outcomes into steps, "
            "ask before consequential actions, ship the deliverable."
        ),
        lens="AI that gets everyday tasks done — polished docs, not to-do lists.",
        toolset="full",
        weight=1.3,
        color="#fb923c",
        icon="👷",
    ),
    Seat(
        id="grok",
        name="Grok",
        title="Coding Harness & Shell",
        project="xai-org/grok-build",
        url="https://github.com/xai-org/grok-build",
        mandate=(
            "Own the code path: edit files, run shell, search, long tasks. "
            "Be aggressive about implement → test → verify loops."
        ),
        lens="Terminal-native coding agent — fullscreen TUI energy, ship code.",
        toolset="coding",
        weight=1.4,
        color="#e2e8f0",
        icon="⚡",
    ),
    Seat(
        id="notebook",
        name="Notebook",
        title="Research Synthesizer",
        project="google-notebook / evidence seat",
        url="https://notebooklm.google.com",
        mandate=(
            "Ground claims in evidence. Structure findings, cite sources, "
            "write clean research notes and reports the rest can act on."
        ),
        lens="Sources first — synthesize, don't hallucinate.",
        toolset="research",
        weight=1.2,
        color="#f472b6",
        icon="📓",
    ),
]


# ── Data model ──────────────────────────────────────────────────────────────

@dataclass
class Opinion:
    seat_id: str
    seat_name: str
    round: str
    stance: str
    summary: str
    points: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    confidence: float = 0.7
    vote: Optional[str] = None
    weight: float = 1.0
    project: str = ""
    ts: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CouncilSession:
    id: str
    goal: str
    status: str = "queued"
    seats: List[str] = field(default_factory=list)
    rounds: List[str] = field(default_factory=list)
    opinions: List[Opinion] = field(default_factory=list)
    proposals: List[dict] = field(default_factory=list)
    tally: Dict[str, float] = field(default_factory=dict)
    consensus: str = ""
    directive: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    dissent: List[str] = field(default_factory=list)
    created_at: str = ""
    finished_at: str = ""
    auto_execute: bool = True
    max_rounds: int = 3

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status,
            "seats": self.seats,
            "rounds": self.rounds,
            "opinions": [o.to_dict() for o in self.opinions],
            "proposals": self.proposals,
            "tally": self.tally,
            "consensus": self.consensus,
            "directive": self.directive,
            "execution": self.execution,
            "dissent": self.dissent,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "auto_execute": self.auto_execute,
            "opinion_count": len(self.opinions),
            "mission_id": self.id,
            "members": [
                {
                    "id": s,
                    "name": DEFAULT_SEAT_INDEX[s].name if s in DEFAULT_SEAT_INDEX else s,
                    "project": DEFAULT_SEAT_INDEX[s].project if s in DEFAULT_SEAT_INDEX else "",
                    "url": DEFAULT_SEAT_INDEX[s].url if s in DEFAULT_SEAT_INDEX else "",
                }
                for s in self.seats
            ],
        }


DEFAULT_SEAT_INDEX = {s.id: s for s in DEFAULT_SEATS}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Offline persona minds (project-flavored) ────────────────────────────────

class PersonaMind:
    """Heuristic opinions that stay in each project's character offline."""

    def brief(self, seat: Seat, goal: str) -> Opinion:
        g = goal.lower()
        points, risks, actions = [], [], []
        stance = "info"

        if seat.id == "prime":
            points = [
                f"Quality gate on: {goal[:70]}",
                "Demand durable decision log + success criteria before build.",
                "Thin plans fail the gate — need recursive improvement loop.",
            ]
            actions = [
                "Write done-criteria to workspace",
                "Persist decision rules in memory",
                "Require a verify step",
            ]
            stance = "amend"
            risks = ["No permanent memory of this decision unless we write it down."]

        elif seat.id == "zero":
            points = [
                "Don't just chat — drive tools: shell, files, browser, code.",
                "Delegate sub-tasks to focused workers when the goal spans domains.",
            ]
            actions = ["terminal/system check", "execute_code or calculator as needed", "write artifacts"]
            stance = "support"
            if any(k in g for k in ("research", "browse", "web")):
                actions = ["web_search", "http_fetch top source", "write report"] + actions

        elif seat.id == "buzz":
            points = [
                "Make the work multiplayer-auditable — clear steps others can join.",
                "Human-in-the-loop on consequential actions.",
            ]
            actions = ["Log plan as shared event trail", "Surface approval points"]
            stance = "amend"
            risks = ["Black-box solo runs break team trust."]

        elif seat.id == "hermes":
            points = [
                "Narrow core, capability at edges — tools + skills + memory.",
                "Promote successful runs into skills; recall past missions.",
            ]
            actions = [
                "Use skill_view if a matching skill exists",
                "memory_store key findings",
                "Keep tool schema lean",
            ]
            stance = "support"

        elif seat.id == "qm":
            points = [
                "Scope the work: personal vs shared artifacts.",
                "Prefer reusable skills packs and scheduled follow-ups.",
            ]
            actions = ["Define owner + shared outputs", "Save a skill if the path works"]
            stance = "support"

        elif seat.id == "eve":
            points = [
                "Filesystem is the interface — instructions, tools, skills as files.",
                "Every durable output should land in the workspace tree.",
            ]
            actions = ["write_file plans/<slug>.md", "Keep artifacts git-friendly"]
            stance = "support"

        elif seat.id == "odysseus":
            points = [
                "Keep research + docs in the local workspace.",
                "Prefer self-hosted paths; minimize unnecessary external leakage.",
            ]
            actions = ["web_search if needed", "write_file reports/", "memory_store summary"]
            stance = "support" if any(k in g for k in ("research", "report", "note", "doc")) else "amend"

        elif seat.id == "openworker":
            points = [
                "Outcome = finished deliverable, not a chat summary.",
                "Break into steps; ship the artifact; confirm before irreversible acts.",
            ]
            actions = ["Name the deliverable", "Execute steps", "Return the finished file/path"]
            stance = "support"

        elif seat.id == "grok":
            points = [
                "If code is involved: implement → run → fix → verify.",
                "Shell + sandbox Python are first-class weapons.",
            ]
            actions = ["execute_code / calculator", "terminal for system facts", "patch until green"]
            stance = "support"
            if any(k in g for k in ("calculate", "fib", "code", "build", "script", "benchmark")):
                stance = "support"
                actions = ["calculator or execute_code", "Print numeric/result", "Finish"]

        else:  # notebook
            points = [
                "Ground claims in search/fetch evidence.",
                "Structure findings before anyone builds on them.",
            ]
            actions = ["web_search", "http_fetch if URL exists", "write_file reports/<slug>.md"]
            stance = "support" if any(k in g for k in ("research", "report", "what is", "explain", "analyze")) else "amend"

        # Goal-specific overrides shared across seats
        if any(k in g for k in ("calculate", "fibonacci", "math", "compute")):
            if seat.id in ("grok", "zero", "openworker", "hermes"):
                actions = ["calculator or execute_code", "Print the number", "Finish"]
                stance = "support"
        if any(k in g for k in ("hide", "steg", "secret", "encrypt")):
            if seat.id in ("zero", "hermes", "prime", "openworker"):
                actions = ["steganography encode", "Return encoded cover text"]
                stance = "support"
        if any(k in g for k in ("hack", "exploit", "malware", "steal", "weapon", "ddos", "phish")):
            if seat.id in ("prime", "hermes", "buzz", "qm"):
                stance = "oppose"
                risks = ["Harmful intent — veto and offer a safe alternative."]
                points = ["Refuse abuse paths. Redirect to defensive/educational framing only."]
                actions = ["Block execution", "Explain policy"]

        return Opinion(
            seat_id=seat.id,
            seat_name=seat.name,
            round="brief",
            stance=stance,
            summary=f"{seat.name} [{seat.project}]: {points[0] if points else seat.mandate}",
            points=points,
            risks=risks,
            actions=actions,
            confidence=0.76,
            weight=seat.weight,
            project=seat.project,
            ts=_now(),
        )

    def propose(self, seat: Seat, goal: str, briefs: List[Opinion]) -> Opinion:
        own = next((b for b in briefs if b.seat_id == seat.id), None)
        actions = list(own.actions if own else [])

        # OpenWorker + Hermes synthesize a merged execution spine
        if seat.id in ("openworker", "hermes", "zero"):
            bag: List[str] = []
            for b in briefs:
                for a in b.actions:
                    if a not in bag and "block" not in a.lower():
                        bag.append(a)
            actions = bag[:8] or actions

        if seat.id == "grok" and not actions:
            actions = ["execute_code", "terminal smoke", "write result file"]
        if seat.id == "notebook" and not actions:
            actions = ["web_search topic", "write_file reports/", "memory_store"]
        if seat.id == "eve" and not actions:
            actions = ["write_file plans/goal.md", "list_files", "verify artifact exists"]
        if seat.id == "prime":
            # quality gate proposal always injects verify + persist
            base = actions or ["Execute core path"]
            actions = base + ["Verify output", "memory_store decision"]
            # unique
            seen = set()
            actions = [a for a in actions if not (a in seen or seen.add(a))]

        return Opinion(
            seat_id=seat.id,
            seat_name=seat.name,
            round="propose",
            stance="support",
            summary=f"{seat.name} plan: {' → '.join(actions[:4]) or goal[:60]}",
            points=[f"Step: {s}" for s in actions],
            actions=actions,
            confidence=0.74,
            weight=seat.weight,
            project=seat.project,
            ts=_now(),
        )

    def critique(self, seat: Seat, goal: str, proposals: List[Opinion]) -> Opinion:
        risks, points, actions = [], [], []
        stance = "amend"
        g = goal.lower()

        if seat.id == "prime":
            for p in proposals:
                if len(p.actions) < 2:
                    risks.append(f"{p.seat_name}'s plan is too thin for the quality gate.")
                joined = " ".join(p.actions).lower()
                if "verif" not in joined and "test" not in joined and "finish" not in joined:
                    risks.append(f"{p.seat_name} lacks verify/finish — gate fails.")
            if not risks:
                risks = ["Gate passes with conditions: persist decision + verify artifact."]
            points = ["Prime gate: require verify step + workspace artifact + memory write."]
            actions = ["Add verify step", "memory_store outcome"]
            stance = "amend"

        elif seat.id == "buzz":
            points = ["Is this auditable for a human teammate joining mid-flight?"]
            risks = ["Missing approval checkpoint on consequential side-effects."]
            actions = ["Mark human-approval points"]
            stance = "amend"

        elif seat.id == "hermes":
            points = ["Keep core lean — don't invent new tools when files+shell suffice."]
            risks = ["Context bloat if we dump every intermediate thought into memory."]
            stance = "support"

        elif seat.id in ("qm", "odysseus"):
            points = ["Scope outputs: what is personal vs shared workspace?"]
            stance = "support"

        elif seat.id == "eve":
            points = ["Every durable step should produce a file path we can open."]
            risks = ["Plans that live only in chat die with the session."]
            actions = ["write_file the plan and the result"]
            stance = "amend"

        elif seat.id == "grok":
            points = ["If there's code, I want a green run in the sandbox before we call done."]
            stance = "support"

        elif seat.id == "notebook":
            points = ["Claims without search/fetch are provisional."]
            if any(k in g for k in ("research", "report", "analyze")):
                risks = ["Skipping evidence pass weakens the deliverable."]
                actions = ["Force web_search before write_file"]
                stance = "amend"
            else:
                stance = "support"

        elif seat.id == "openworker":
            best = max(proposals, key=lambda p: len(p.actions)) if proposals else None
            points = [
                f"Pick the plan that ends in a finished artifact"
                + (f" — leaning {best.seat_name}." if best else ".")
            ]
            stance = "support"

        else:  # zero
            points = ["Enough talk — ensure the exec path actually calls tools."]
            stance = "support"

        # harm veto from quality/collab seats
        if any(k in g for k in ("hack", "exploit", "malware", "steal", "weapon", "ddos", "phish")):
            if seat.id in ("prime", "hermes", "buzz", "qm", "openworker"):
                stance = "oppose"
                points = ["Veto: harmful goal. Refuse and offer defensive alternative only."]
                risks = ["Abuse / unauthorized access path."]
                actions = ["Block execution"]

        return Opinion(
            seat_id=seat.id,
            seat_name=seat.name,
            round="critique",
            stance=stance,
            summary=points[0] if points else f"{seat.name} critique",
            points=points,
            risks=risks,
            actions=actions,
            confidence=0.78,
            weight=seat.weight,
            project=seat.project,
            ts=_now(),
        )

    def vote(self, seat: Seat, goal: str, history: List[Opinion]) -> Opinion:
        g = goal.lower()
        harmful = any(
            k in g
            for k in (
                "hack", "exploit", "malware", "steal", "weapon", "harm",
                "ddos", "ransomware", "phish", "credential stuff",
            )
        )
        # Prime hard-veto on harm; also if Prime/Hermes opposed in critique
        gate_oppose = harmful or any(
            o.stance == "oppose" and o.seat_id in ("prime", "hermes", "buzz")
            for o in history
        )

        if gate_oppose and seat.id in ("prime", "hermes", "buzz", "qm", "openworker", "zero"):
            vote, stance = "reject", "oppose"
            summary = f"{seat.name} votes REJECT — safety/quality gate."
        elif seat.id == "prime":
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "verif" in text or "memory_store" in text or "finish" in text or "report" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE — gate conditions met."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — add verify + persist."
        elif seat.id == "notebook" and any(k in g for k in ("research", "report")):
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "web_search" in text or "search" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE — evidence path present."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — need evidence pass."
        else:
            vote, stance = "approve", "support"
            summary = f"{seat.name} votes APPROVE."

        actions: List[str] = []
        for prefer in ("openworker", "hermes", "zero", "grok", "notebook", "eve", "prime"):
            for o in history:
                if o.round == "propose" and o.seat_id == prefer:
                    for a in o.actions:
                        if a not in actions:
                            actions.append(a)

        return Opinion(
            seat_id=seat.id,
            seat_name=seat.name,
            round="vote",
            stance=stance,
            summary=summary,
            points=[summary],
            actions=actions[:8],
            vote=vote,
            confidence=0.82,
            weight=seat.weight,
            project=seat.project,
            ts=_now(),
        )


# ── Council engine ──────────────────────────────────────────────────────────

class AgentCouncil:
    """Convenor — runs multi-project deliberation then optional execution."""

    def __init__(
        self,
        session_db=None,
        vector=None,
        skills=None,
        memory_provider=None,
        brain: Optional[LLMBrain] = None,
        event_cb: Optional[EventCB] = None,
        seats: Optional[List[Seat]] = None,
        executor_factory: Optional[Callable[..., Any]] = None,
    ):
        self.session_db = session_db
        self.vector = vector
        self.skills = skills
        self.memory_provider = memory_provider
        self.brain = brain or LLMBrain()
        self.event_cb = event_cb
        self.seats = {s.id: s for s in (seats or DEFAULT_SEATS)}
        self.executor_factory = executor_factory
        self.sessions: Dict[str, CouncilSession] = {}
        self._lock = threading.Lock()
        self._mind = PersonaMind()
        self._cancel: Set[str] = set()

    def list_seats(self) -> List[dict]:
        return [asdict(s) for s in self.seats.values()]

    def list_sessions(self) -> List[dict]:
        with self._lock:
            return [
                s.to_dict()
                for s in sorted(
                    self.sessions.values(), key=lambda x: x.created_at, reverse=True
                )
            ]

    def get(self, cid: str) -> Optional[dict]:
        s = self.sessions.get(cid)
        return s.to_dict() if s else None

    def cancel(self, cid: str) -> bool:
        if cid in self.sessions and self.sessions[cid].status in (
            "queued", "deliberating", "executing",
        ):
            self._cancel.add(cid)
            return True
        return False

    def _emit(self, kind: str, session: CouncilSession, **payload):
        event = {
            "type": kind,
            "ts": _now(),
            "mission_id": session.id,
            "session_id": session.id,
            "council_id": session.id,
            "goal": session.goal,
            **payload,
        }
        if self.event_cb:
            try:
                self.event_cb(event)
            except Exception:
                pass
        if self.session_db:
            try:
                self.session_db.log_event(kind, json.dumps(payload)[:500], session.id)
            except Exception:
                pass

    def convene(
        self,
        goal: str,
        seat_ids: Optional[List[str]] = None,
        auto_execute: bool = True,
        background: bool = True,
        max_rounds: int = 3,
    ) -> dict:
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("goal required")

        ids = seat_ids or list(self.seats.keys())
        ids = [i for i in ids if i in self.seats] or list(self.seats.keys())

        cid = uuid.uuid4().hex[:12]
        session = CouncilSession(
            id=cid,
            goal=goal,
            status="queued",
            seats=ids,
            created_at=_now(),
            auto_execute=auto_execute,
            max_rounds=max(1, min(int(max_rounds or 3), 5)),
        )
        with self._lock:
            self.sessions[cid] = session

        if self.session_db:
            try:
                self.session_db.new_session(
                    goal=f"[council] {goal}", role="council", title=f"Council {cid}"
                )
            except Exception:
                pass

        self._emit("council_queued", session, seats=ids)

        if background:
            t = threading.Thread(target=self._run, args=(cid,), daemon=True)
            t.start()
            return session.to_dict()
        return self._run(cid)

    def _run(self, cid: str) -> dict:
        session = self.sessions[cid]
        session.status = "deliberating"
        self._emit("council_started", session)
        members = [
            f"{self.seats[i].icon} {self.seats[i].name}" for i in session.seats
        ]
        self._emit(
            "thought",
            session,
            step=0,
            thought=f"Council seated ({len(members)}): " + ", ".join(members),
            action="convene",
            args={"seats": session.seats, "projects": [self.seats[i].project for i in session.seats]},
        )

        try:
            seats = [self.seats[i] for i in session.seats]

            # 1 BRIEF
            session.rounds.append("brief")
            self._emit("council_round", session, round="brief", message="Opening briefs from each project seat")
            briefs = self._parallel_opinions(seats, "brief", session)
            session.opinions.extend(briefs)
            for op in briefs:
                self._emit_opinion(session, op, step=1)
            if cid in self._cancel:
                return self._cancelled(session)

            # 2 PROPOSE — builders + synthesizers
            proposers = [
                s for s in seats
                if s.id in ("hermes", "zero", "grok", "openworker", "notebook", "eve", "prime", "odysseus")
            ] or seats[:5]
            session.rounds.append("propose")
            self._emit("council_round", session, round="propose", message="Project proposals")
            proposals = self._parallel_opinions(proposers, "propose", session, prior=briefs)
            session.opinions.extend(proposals)
            session.proposals = [
                {
                    "seat": p.seat_id,
                    "name": p.seat_name,
                    "project": p.project,
                    "steps": p.actions,
                    "summary": p.summary,
                }
                for p in proposals
            ]
            for op in proposals:
                self._emit_opinion(session, op, step=2)
            if cid in self._cancel:
                return self._cancelled(session)

            # 3 CRITIQUE — quality + collab + evidence
            critics = [
                s for s in seats
                if s.id in ("prime", "hermes", "buzz", "qm", "eve", "notebook", "openworker")
            ] or seats
            session.rounds.append("critique")
            self._emit("council_round", session, round="critique", message="Cross-project critique")
            critiques = self._parallel_opinions(critics, "critique", session, prior=session.opinions)
            session.opinions.extend(critiques)
            for op in critiques:
                self._emit_opinion(session, op, step=3)
            if cid in self._cancel:
                return self._cancelled(session)

            # 4 VOTE — all seats
            session.rounds.append("vote")
            session.status = "voted"
            self._emit("council_round", session, round="vote", message="Final weighted vote")
            votes = self._parallel_opinions(seats, "vote", session, prior=session.opinions)
            session.opinions.extend(votes)
            for op in votes:
                self._emit_opinion(session, op, step=4)

            tally = {"approve": 0.0, "reject": 0.0, "amend": 0.0}
            for v in votes:
                key = v.vote or "amend"
                tally[key] = tally.get(key, 0.0) + float(v.weight or 1.0)
            session.tally = tally
            winner = max(tally, key=tally.get)

            # Prime hard-veto on reject
            prime_veto = any(v.seat_id == "prime" and v.vote == "reject" for v in votes)
            hermes_veto = any(v.seat_id == "hermes" and v.vote == "reject" for v in votes)
            if prime_veto or hermes_veto:
                winner = "reject"

            session.dissent = [
                f"{v.seat_name} ({v.project}): {v.summary}"
                for v in votes
                if v.vote and v.vote != winner
            ]
            if prime_veto:
                session.dissent.insert(0, "Prime hard-veto: quality/safety gate rejected the goal.")
            if hermes_veto:
                session.dissent.insert(0, "Hermes hard-veto: learning-core safety reject.")

            session.directive = self._build_directive(session, votes, winner)
            session.consensus = session.directive.get("summary", winner)
            self._emit(
                "council_consensus",
                session,
                tally=tally,
                winner=winner,
                directive=session.directive,
                dissent=session.dissent,
            )
            self._emit(
                "thought",
                session,
                step=5,
                thought=f"Consensus: {winner} — {session.consensus[:160]}",
                action="consensus",
                args=tally,
            )

            if session.auto_execute and winner != "reject":
                session.status = "executing"
                self._emit("council_executing", session, message="Vortex chief executing council directive")
                session.execution = self._execute_directive(session)
                result_text = self._format_result(session)
                session.status = "completed"
                session.finished_at = _now()
                self._remember(session)
                self._emit("mission_completed", session, result=result_text, steps=len(session.opinions))
                self._emit("council_completed", session, result=result_text)
            elif winner == "reject":
                session.status = "completed"
                session.finished_at = _now()
                session.execution = {
                    "status": "blocked",
                    "reason": "Council rejected the goal.",
                    "dissent": session.dissent,
                }
                result_text = self._format_result(session)
                self._emit("mission_completed", session, result=result_text, steps=len(session.opinions))
                self._emit("council_completed", session, result=result_text)
            else:
                session.status = "completed"
                session.finished_at = _now()
                result_text = self._format_result(session)
                self._emit("mission_completed", session, result=result_text, steps=len(session.opinions))
                self._emit("council_completed", session, result=result_text)

            return session.to_dict()

        except Exception as e:
            session.status = "failed"
            session.finished_at = _now()
            session.execution = {"status": "failed", "error": str(e)}
            self._emit("mission_failed", session, error=str(e))
            self._emit("council_failed", session, error=str(e))
            return session.to_dict()
        finally:
            self._cancel.discard(cid)

    def _cancelled(self, session: CouncilSession) -> dict:
        session.status = "cancelled"
        session.finished_at = _now()
        self._emit("mission_cancelled", session)
        self._emit("council_cancelled", session)
        return session.to_dict()

    def _parallel_opinions(
        self,
        seats: List[Seat],
        round_name: str,
        session: CouncilSession,
        prior: Optional[List[Opinion]] = None,
    ) -> List[Opinion]:
        prior = prior or []

        def one(seat: Seat) -> Opinion:
            if self.brain.provider != "offline":
                try:
                    return self._llm_opinion(seat, round_name, session.goal, prior)
                except Exception:
                    pass
            return self._offline_opinion(seat, round_name, session.goal, prior)

        out: List[Opinion] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(seats) or 1)) as pool:
            futs = {pool.submit(one, s): s for s in seats}
            for fut in concurrent.futures.as_completed(futs):
                try:
                    out.append(fut.result())
                except Exception as e:
                    s = futs[fut]
                    out.append(
                        Opinion(
                            seat_id=s.id,
                            seat_name=s.name,
                            round=round_name,
                            stance="abstain",
                            summary=f"{s.name} errored: {e}",
                            weight=s.weight,
                            project=s.project,
                            ts=_now(),
                        )
                    )
        order = {s.id: i for i, s in enumerate(seats)}
        out.sort(key=lambda o: order.get(o.seat_id, 99))
        return out

    def _offline_opinion(
        self, seat: Seat, round_name: str, goal: str, prior: List[Opinion]
    ) -> Opinion:
        if round_name == "brief":
            return self._mind.brief(seat, goal)
        if round_name == "propose":
            return self._mind.propose(seat, goal, [o for o in prior if o.round == "brief"])
        if round_name == "critique":
            return self._mind.critique(seat, goal, [o for o in prior if o.round == "propose"])
        if round_name == "vote":
            return self._mind.vote(seat, goal, prior)
        return self._mind.brief(seat, goal)

    def _llm_opinion(
        self, seat: Seat, round_name: str, goal: str, prior: List[Opinion]
    ) -> Opinion:
        prior_txt = "\n".join(
            f"- [{o.round}/{o.seat_name}@{o.project}] ({o.stance}) {o.summary}"
            for o in prior[-16:]
        )
        prompt = (
            f"{seat.system_block()}\n\n"
            f"Council goal: {goal}\n"
            f"Round: {round_name}\n"
            f"Prior opinions:\n{prior_txt or '(none)'}\n\n"
            "Reply ONLY JSON:\n"
            '{"stance":"support|oppose|amend|abstain|info",'
            '"summary":"one line",'
            '"points":["..."],'
            '"risks":["..."],'
            '"actions":["..."],'
            '"vote":"approve|reject|amend|null",'
            '"confidence":0.0}\n'
        )
        raw = self.brain.chat(
            [{"role": "user", "content": prompt}],
            system="You are a council member embodying an open-source agent project. JSON only.",
        )
        m = re.search(r"\{.*\}", raw or "", re.S)
        data = {}
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                data = {}
        return Opinion(
            seat_id=seat.id,
            seat_name=seat.name,
            round=round_name,
            stance=data.get("stance") or "info",
            summary=data.get("summary") or f"{seat.name} on {round_name}",
            points=list(data.get("points") or [])[:8],
            risks=list(data.get("risks") or [])[:6],
            actions=list(data.get("actions") or [])[:8],
            vote=data.get("vote"),
            confidence=float(data.get("confidence") or 0.7),
            weight=seat.weight,
            project=seat.project,
            ts=_now(),
        )

    def _emit_opinion(self, session: CouncilSession, op: Opinion, step: int):
        self._emit(
            "council_opinion",
            session,
            step=step,
            seat=op.seat_id,
            seat_name=op.seat_name,
            project=op.project,
            round=op.round,
            stance=op.stance,
            summary=op.summary,
            points=op.points,
            risks=op.risks,
            actions=op.actions,
            vote=op.vote,
            weight=op.weight,
        )
        self._emit(
            "thought",
            session,
            step=step,
            thought=f"{op.seat_name} ({op.project}) · {op.round}: {op.summary}",
            action=f"council:{op.round}",
            args={"seat": op.seat_id, "project": op.project, "stance": op.stance, "vote": op.vote},
        )
        if op.actions:
            self._emit(
                "observation",
                session,
                step=step,
                tool=f"council:{op.seat_id}",
                status="success",
                observation=f"OK — {op.stance}: {'; '.join(op.actions[:4])}",
            )

    def _build_directive(
        self, session: CouncilSession, votes: List[Opinion], winner: str
    ) -> dict:
        ranked_actions: List[str] = []
        for prefer in (
            "openworker", "hermes", "zero", "grok", "notebook",
            "eve", "odysseus", "prime", "qm", "buzz",
        ):
            for o in session.opinions:
                if o.seat_id == prefer and o.actions:
                    for a in o.actions:
                        if a not in ranked_actions and "block" not in a.lower():
                            ranked_actions.append(a)
        for o in session.opinions:
            if o.round == "critique" and o.stance in ("amend", "oppose"):
                for a in o.actions:
                    if a not in ranked_actions:
                        ranked_actions.append(a)

        risks = []
        for o in session.opinions:
            for r in o.risks:
                if r not in risks:
                    risks.append(r)

        members = [
            f"{self.seats[i].name} ({self.seats[i].project})"
            for i in session.seats
            if i in self.seats
        ]
        summary = (
            f"Council {winner.upper()} on «{session.goal[:80]}» — "
            f"{len(ranked_actions)} action(s), {len(session.seats)} project seats."
        )
        exec_goal = self._actions_to_goal(session.goal, ranked_actions, winner)

        return {
            "decision": winner,
            "summary": summary,
            "actions": ranked_actions[:12],
            "risks": risks[:10],
            "tally": session.tally,
            "dissent": session.dissent,
            "exec_goal": exec_goal,
            "seats": session.seats,
            "members": members,
        }

    def _actions_to_goal(self, original: str, actions: List[str], winner: str) -> str:
        if winner == "reject":
            return f"Do not execute. Explain why the council blocked: {original}"
        low = original.lower()
        if any(
            k in low
            for k in (
                "calculate", "fibonacci", "compute", "hide", "steganograph",
                "system info", "translate", "research", "report", "build",
                "write", "analyze", "investigate",
            )
        ):
            return original.strip()
        useful = [
            a for a in actions
            if a
            and not a.lower().startswith("add verify")
            and "sandbox" not in a.lower()
            and "exfiltrat" not in a.lower()
            and "block" not in a.lower()
            and "human-approval" not in a.lower()
            and "approval point" not in a.lower()
        ]
        if useful:
            return f"{original.strip()}. Council plan: {'; '.join(useful[:6])}."
        return original

    def _execute_directive(self, session: CouncilSession) -> dict:
        directive = session.directive or {}
        exec_goal = directive.get("exec_goal") or session.goal
        if not self.executor_factory:
            return {
                "status": "no_executor",
                "result": json.dumps(directive, indent=2),
                "goal": exec_goal,
            }
        try:
            agent = self.executor_factory()
            agent.event_cb = self.event_cb
            result = agent.run(exec_goal, background=False, max_steps=12)
            return {
                "status": result.get("status"),
                "mission_id": result.get("id"),
                "result": result.get("result") or result.get("error") or "",
                "steps": result.get("step_count"),
                "goal": exec_goal,
            }
        except Exception as e:
            return {"status": "failed", "error": str(e), "goal": exec_goal}

    def _format_result(self, session: CouncilSession) -> str:
        d = session.directive or {}
        ex = session.execution or {}
        lines = [
            "# ⚖ Vortex Agent Council — Verdict",
            f"**Goal:** {session.goal}",
            f"**Decision:** {(d.get('decision') or session.status).upper()}",
            f"**Tally:** " + ", ".join(f"{k}={v:.1f}" for k, v in (session.tally or {}).items()),
            "",
            "## Seated projects",
        ]
        for sid in session.seats:
            s = self.seats.get(sid)
            if s:
                lines.append(f"- {s.icon} **{s.name}** — [{s.project}]({s.url})")
        lines += ["", "## Consensus", d.get("summary") or session.consensus or "—", "", "## Action plan"]
        for i, a in enumerate(d.get("actions") or [], 1):
            lines.append(f"{i}. {a}")
        if d.get("risks"):
            lines += ["", "## Risks"]
            for r in d["risks"]:
                lines.append(f"- ⚠ {r}")
        if session.dissent:
            lines += ["", "## Dissent"]
            for x in session.dissent:
                lines.append(f"- {x}")
        lines += ["", "## Execution"]
        if ex.get("status") == "blocked":
            lines.append(f"Blocked: {ex.get('reason')}")
        else:
            lines.append(f"Status: {ex.get('status', 'n/a')} · mission={ex.get('mission_id', '—')}")
            body = (ex.get("result") or ex.get("error") or "").strip()
            if body:
                lines += ["", "### Chief output", body[:3000]]
        lines += ["", f"_Rounds: {', '.join(session.rounds)}_"]
        return "\n".join(lines)

    def _remember(self, session: CouncilSession):
        try:
            if self.vector:
                self.vector.remember(
                    f"[council:{session.id}] {session.goal} => "
                    f"{(session.directive or {}).get('decision')} "
                    f"{(session.execution or {}).get('status')}",
                    {"council": session.id},
                )
            if self.skills:
                steps = [f"{o.seat_id}:{o.round}" for o in session.opinions[:24]]
                self.skills.save_learned(
                    f"council_{session.id}",
                    f"Council on: {session.goal[:100]}",
                    steps,
                )
            if self.memory_provider and hasattr(self.memory_provider, "write"):
                self.memory_provider.write(
                    f"Council {session.id} decided "
                    f"{(session.directive or {}).get('decision')} on: {session.goal[:120]}",
                    tag="council",
                )
        except Exception:
            pass
