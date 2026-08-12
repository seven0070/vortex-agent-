"""AI Agent Council — multi-persona deliberation under the autonomous chief.

Architecture (Hermes waist + council edge):

    User goal
        │
        ▼
    Chief (AIAgent)  ──optional──►  convene_council
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
              Researcher          Architect            Critic …
                    │                   │                   │
                    └────────►  rounds: brief → propose → critique
                                        → rebut → vote → consensus
                                        │
                                        ▼
                              Directive (plan + risks + vote tally)
                                        │
                                        ▼
                              Chief executes via tools / subagents

Each seat has a persona, toolset bias, and vote weight. Deliberation is
parallel where safe, sequential where critique depends on proposals.
Works fully offline via persona heuristics; upgrades automatically when
an LLM provider is configured.
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from vortex.agent.llm import LLMBrain, parse_action


EventCB = Callable[[dict], None]


# ── Personas ────────────────────────────────────────────────────────────────

@dataclass
class Seat:
    """One chair at the council table."""
    id: str
    name: str
    title: str
    mandate: str                 # what this seat optimizes for
    lens: str                    # how they frame problems
    toolset: str                 # preferred toolset when executing
    weight: float = 1.0          # vote weight
    color: str = "#f97316"       # UI accent
    icon: str = "◆"

    def system_block(self) -> str:
        return (
            f"You are {self.name}, {self.title} on the Vortex Agent Council.\n"
            f"Mandate: {self.mandate}\n"
            f"Lens: {self.lens}\n"
            f"Be pointed, concrete, and brief. No fluff."
        )


DEFAULT_SEATS: List[Seat] = [
    Seat(
        id="strategist",
        name="Atlas",
        title="Chief Strategist",
        mandate="Frame the goal, success criteria, constraints, and sequencing.",
        lens="Systems thinking — decompose, prioritize, define done.",
        toolset="full",
        weight=1.3,
        color="#a78bfa",
        icon="♟",
    ),
    Seat(
        id="researcher",
        name="Lyra",
        title="Research Lead",
        mandate="Gather evidence, cite findings, surface unknowns.",
        lens="Evidence first — search, verify, never invent sources.",
        toolset="research",
        weight=1.1,
        color="#22d3ee",
        icon="🔍",
    ),
    Seat(
        id="architect",
        name="Forge",
        title="Systems Architect",
        mandate="Design the technical path: components, interfaces, code.",
        lens="Buildability — prefer simple, testable, reversible steps.",
        toolset="coding",
        weight=1.2,
        color="#fbbf24",
        icon="⚙",
    ),
    Seat(
        id="critic",
        name="Vex",
        title="Red Team Critic",
        mandate="Attack weak plans, find failure modes, demand proof.",
        lens="Adversarial — assume the plan is wrong until shown otherwise.",
        toolset="core",
        weight=1.4,
        color="#f87171",
        icon="⚔",
    ),
    Seat(
        id="ethicist",
        name="Aegis",
        title="Safety & Ethics",
        mandate="Flag harm, privacy, abuse, irreversible risk.",
        lens="Do no harm — block or constrain dangerous paths.",
        toolset="security",
        weight=1.5,
        color="#34d399",
        icon="🛡",
    ),
    Seat(
        id="cipher",
        name="Shade",
        title="Security Counsel",
        mandate="Threat model, secrets handling, least privilege.",
        lens="Zero trust — minimize exposure, log everything sensitive.",
        toolset="security",
        weight=1.1,
        color="#fb923c",
        icon="🔒",
    ),
    Seat(
        id="executor",
        name="Pulse",
        title="Execution Officer",
        mandate="Turn consensus into a concrete, ordered action plan.",
        lens="Ship it — clear steps, owners, tools, exit criteria.",
        toolset="full",
        weight=1.0,
        color="#f97316",
        icon="⚡",
    ),
]


# ── Data model ──────────────────────────────────────────────────────────────

@dataclass
class Opinion:
    seat_id: str
    seat_name: str
    round: str                   # brief|propose|critique|rebut|vote
    stance: str                  # support|oppose|amend|abstain|info
    summary: str
    points: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    confidence: float = 0.7
    vote: Optional[str] = None   # approve|reject|amend
    weight: float = 1.0
    ts: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CouncilSession:
    id: str
    goal: str
    status: str = "queued"       # queued|deliberating|voted|executing|completed|failed
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
            "mission_id": self.id,  # UI event compat
        }


# ── Offline persona brains ──────────────────────────────────────────────────

class PersonaMind:
    """Heuristic opinions when no LLM key is set — still produces real structure."""

    def brief(self, seat: Seat, goal: str) -> Opinion:
        g = goal.lower()
        points, risks, actions = [], [], []
        stance = "info"

        if seat.id == "strategist":
            points = [
                f"Success = measurable outcome for: {goal[:80]}",
                "Break into discover → decide → deliver → verify.",
                "Prefer the smallest plan that can be proven.",
            ]
            actions = ["Define done-criteria", "Order work by risk-reduction first"]
            stance = "support"
        elif seat.id == "researcher":
            points = [
                "Need external signal before committing to a single path.",
                "Unknowns should be listed explicitly and closed with tools.",
            ]
            actions = ["web_search the core topic", "Write findings to reports/"]
            if any(k in g for k in ("research", "what is", "explain", "analyze", "report")):
                stance = "support"
            else:
                stance = "amend"
                points.append("Even non-research goals benefit from a 60s evidence pass.")
        elif seat.id == "architect":
            points = [
                "Technical path should be tool-native (code, files, shell).",
                "Each step needs an observable exit signal.",
            ]
            actions = ["Draft ordered tool sequence", "Keep artifacts in workspace"]
            if any(k in g for k in ("build", "code", "implement", "script", "calculate", "fib")):
                stance = "support"
            else:
                stance = "amend"
        elif seat.id == "critic":
            risks = [
                "Plan may skip verification.",
                "Single-path thinking — no fallback if step 1 fails.",
                "Ambiguous success criteria invite thrash.",
            ]
            points = ["I oppose any plan without a verify step and a kill condition."]
            actions = ["Add verify step", "Add fallback if primary path fails"]
            stance = "amend"
        elif seat.id == "ethicist":
            risks = []
            if any(k in g for k in ("hack", "exploit", "malware", "steal", "weapon", "harm")):
                stance = "oppose"
                risks = ["Request may involve harm or abuse — block or heavily constrain."]
                points = ["Refuse harmful interpretations; offer a safe alternative."]
            else:
                stance = "support"
                points = ["No clear harm vector detected.", "Keep secrets out of logs where possible."]
                actions = ["Avoid exfiltrating personal data", "Use workspace sandbox only"]
        elif seat.id == "cipher":
            points = [
                "Least privilege on shell and files.",
                "Secrets (if any) via stego/memory kv — never plain chat if avoidable.",
            ]
            risks = ["Command injection / path escape if tools misused."]
            actions = ["Prefer allowlisted terminal", "Sandbox code execution"]
            stance = "amend" if "hide" in g or "secret" in g else "support"
        else:  # executor
            points = [
                "I will only run what the vote approves.",
                "Execution plan must be a numbered tool sequence.",
            ]
            actions = ["Compile final directive", "Run with max_steps budget", "Report artifacts"]
            stance = "support"

        # goal-specific spice
        if any(k in g for k in ("calculate", "fib", "math")):
            if seat.id in ("architect", "executor", "strategist"):
                actions = ["calculator or execute_code", "Print numeric result", "Finish"]
                stance = "support"
        if "hide" in g or "steg" in g:
            if seat.id in ("cipher", "executor"):
                actions = ["steganography encode", "Return encoded cover text"]
                stance = "support"
        if any(k in g for k in ("research", "report")):
            if seat.id in ("researcher", "executor", "strategist"):
                actions = [
                    "web_search",
                    "write_file reports/<slug>.md",
                    "memory_store summary",
                ]
                stance = "support"

        return Opinion(
            seat_id=seat.id,
            seat_name=seat.name,
            round="brief",
            stance=stance,
            summary=f"{seat.name} ({seat.title}): {points[0] if points else seat.mandate}",
            points=points,
            risks=risks,
            actions=actions,
            confidence=0.75,
            weight=seat.weight,
            ts=_now(),
        )

    def propose(self, seat: Seat, goal: str, briefs: List[Opinion]) -> Opinion:
        # merge actions from own brief + strategist
        own = next((b for b in briefs if b.seat_id == seat.id), None)
        strat = next((b for b in briefs if b.seat_id == "strategist"), None)
        actions = list(own.actions if own else [])
        if seat.id == "executor" and strat:
            # executor synthesizes
            bag = []
            for b in briefs:
                for a in b.actions:
                    if a not in bag:
                        bag.append(a)
            actions = bag[:8] or actions
        if seat.id == "architect" and not actions:
            actions = ["Decompose into modules", "Implement core path", "Smoke test"]
        if seat.id == "researcher" and not actions:
            actions = ["web_search topic", "http_fetch top source", "write report"]

        plan = {
            "title": f"{seat.name}'s plan",
            "steps": actions or [f"Address goal: {goal[:60]}"],
            "owner": seat.id,
        }
        return Opinion(
            seat_id=seat.id,
            seat_name=seat.name,
            round="propose",
            stance="support",
            summary=f"Proposal: {' → '.join(plan['steps'][:4])}",
            points=[f"Step: {s}" for s in plan["steps"]],
            actions=plan["steps"],
            confidence=0.72,
            weight=seat.weight,
            ts=_now(),
        )

    def critique(self, seat: Seat, goal: str, proposals: List[Opinion]) -> Opinion:
        risks, points = [], []
        stance = "amend"
        if seat.id == "critic":
            for p in proposals:
                if len(p.actions) < 2:
                    risks.append(f"{p.seat_name}'s plan is too thin ({len(p.actions)} steps).")
                if not any("verif" in a.lower() or "test" in a.lower() or "finish" in a.lower() for a in p.actions):
                    risks.append(f"{p.seat_name} lacks a verify/finish step.")
            if not risks:
                risks = ["No catastrophic holes, but demand a concrete success check."]
            points = ["Require: verify step + artifact path + failure fallback."]
            stance = "amend"
        elif seat.id == "ethicist":
            g = goal.lower()
            if any(k in g for k in ("hack", "exploit", "malware", "ddos", "steal")):
                stance = "oppose"
                points = ["Ethical veto: goal collides with harm policy."]
                risks = ["Potential abuse path."]
            else:
                stance = "support"
                points = ["Ethics clear — proceed with sandbox constraints."]
        elif seat.id == "cipher":
            points = ["Confirm tools stay inside workspace and allowlists."]
            risks = ["Watch for secret leakage in final report."]
            stance = "amend"
        else:
            # mild peer review
            best = max(proposals, key=lambda p: len(p.actions)) if proposals else None
            points = [f"Lean toward {best.seat_name}'s plan." if best else "No proposals yet."]
            stance = "support"

        return Opinion(
            seat_id=seat.id,
            seat_name=seat.name,
            round="critique",
            stance=stance,
            summary=points[0] if points else f"{seat.name} critique",
            points=points,
            risks=risks,
            actions=["Add verify step", "Keep sandbox"] if stance == "amend" else [],
            confidence=0.78,
            weight=seat.weight,
            ts=_now(),
        )

    def vote(self, seat: Seat, goal: str, history: List[Opinion]) -> Opinion:
        g = goal.lower()
        # Direct harm signal on the goal itself
        harmful = any(
            k in g
            for k in (
                "hack", "exploit", "malware", "steal", "weapon", "harm",
                "ddos", "ransomware", "phish", "credential stuff",
            )
        )
        eth_opposed = harmful or any(
            o.stance == "oppose" and o.seat_id == "ethicist" for o in history
        )

        if eth_opposed and seat.id in ("ethicist", "critic", "cipher", "strategist"):
            vote = "reject"
            stance = "oppose"
            summary = f"{seat.name} votes REJECT — unresolved safety concerns."
        elif seat.id == "critic":
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "verif" in text or "test" in text or "finish" in text or "report" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE with verify conditions."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — add verification."
        else:
            vote, stance = "approve", "support"
            summary = f"{seat.name} votes APPROVE."

        actions = []
        for o in history:
            if o.round == "propose" and o.seat_id in (
                "executor", "architect", "researcher", "strategist"
            ):
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
            confidence=0.8,
            weight=seat.weight,
            ts=_now(),
        )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Council engine ──────────────────────────────────────────────────────────

class AgentCouncil:
    """Convenor of the table — runs deliberation and optional execution."""

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
        self.executor_factory = executor_factory  # () -> AIAgent
        self.sessions: Dict[str, CouncilSession] = {}
        self._lock = threading.Lock()
        self._mind = PersonaMind()
        self._cancel: Set[str] = set()

    # ── catalog ────────────────────────────────────────────────────────────
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
            "queued",
            "deliberating",
            "executing",
        ):
            self._cancel.add(cid)
            return True
        return False

    # ── events ─────────────────────────────────────────────────────────────
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

    # ── public entry ───────────────────────────────────────────────────────
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
        ids = [i for i in ids if i in self.seats]
        if not ids:
            ids = list(self.seats.keys())

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
                # mirror as a session row for unified history
                self.session_db.new_session(goal=f"[council] {goal}", role="council", title=f"Council {cid}")
            except Exception:
                pass

        self._emit("council_queued", session, seats=ids)

        if background:
            t = threading.Thread(target=self._run, args=(cid,), daemon=True)
            t.start()
            return session.to_dict()
        return self._run(cid)

    # ── deliberation pipeline ──────────────────────────────────────────────
    def _run(self, cid: str) -> dict:
        session = self.sessions[cid]
        session.status = "deliberating"
        self._emit("council_started", session)
        self._emit(
            "thought",
            session,
            step=0,
            thought=f"Council seated: {', '.join(session.seats)}",
            action="convene",
            args={"seats": session.seats},
        )

        try:
            seats = [self.seats[i] for i in session.seats]

            # Round 1 — BRIEF (parallel)
            session.rounds.append("brief")
            self._emit("council_round", session, round="brief", message="Opening briefs")
            briefs = self._parallel_opinions(seats, "brief", session)
            session.opinions.extend(briefs)
            for op in briefs:
                self._emit_opinion(session, op, step=1)

            if cid in self._cancel:
                return self._cancelled(session)

            # Round 2 — PROPOSE (parallel, key seats)
            proposers = [
                s
                for s in seats
                if s.id in ("strategist", "researcher", "architect", "executor", "cipher")
            ]
            if not proposers:
                proposers = seats[:3]
            session.rounds.append("propose")
            self._emit("council_round", session, round="propose", message="Proposals")
            proposals = self._parallel_opinions(
                proposers, "propose", session, prior=briefs
            )
            session.opinions.extend(proposals)
            session.proposals = [
                {
                    "seat": p.seat_id,
                    "name": p.seat_name,
                    "steps": p.actions,
                    "summary": p.summary,
                }
                for p in proposals
            ]
            for op in proposals:
                self._emit_opinion(session, op, step=2)

            if cid in self._cancel:
                return self._cancelled(session)

            # Round 3 — CRITIQUE (critic, ethicist, cipher, strategist)
            critics = [
                s for s in seats if s.id in ("critic", "ethicist", "cipher", "strategist")
            ]
            session.rounds.append("critique")
            self._emit("council_round", session, round="critique", message="Red-team critique")
            critiques = self._parallel_opinions(
                critics, "critique", session, prior=session.opinions
            )
            session.opinions.extend(critiques)
            for op in critiques:
                self._emit_opinion(session, op, step=3)

            if cid in self._cancel:
                return self._cancelled(session)

            # Round 4 — VOTE (all seats)
            session.rounds.append("vote")
            session.status = "voted"
            self._emit("council_round", session, round="vote", message="Final vote")
            votes = self._parallel_opinions(
                seats, "vote", session, prior=session.opinions
            )
            session.opinions.extend(votes)
            for op in votes:
                self._emit_opinion(session, op, step=4)

            # Tally
            tally = {"approve": 0.0, "reject": 0.0, "amend": 0.0}
            for v in votes:
                key = v.vote or "amend"
                tally[key] = tally.get(key, 0.0) + float(v.weight or 1.0)
            session.tally = tally
            winner = max(tally, key=tally.get)

            # Hard veto: ethicist reject always wins (safety seat)
            eth_veto = any(
                v.seat_id == "ethicist" and v.vote == "reject" for v in votes
            )
            if eth_veto:
                winner = "reject"

            # Dissent
            session.dissent = [
                f"{v.seat_name}: {v.summary}"
                for v in votes
                if v.vote and v.vote != winner
            ]
            if eth_veto:
                session.dissent.insert(0, "Aegis hard-veto: ethics seat rejected the goal.")

            # Build consensus directive
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

            # Optional execution by autonomous agent
            if session.auto_execute and winner != "reject":
                session.status = "executing"
                self._emit(
                    "council_executing",
                    session,
                    message="Chief executing council directive",
                )
                session.execution = self._execute_directive(session)
                result_text = self._format_result(session)
                session.status = "completed"
                session.finished_at = _now()
                self._remember(session)
                self._emit(
                    "mission_completed",
                    session,
                    result=result_text,
                    steps=len(session.opinions),
                )
                self._emit(
                    "council_completed",
                    session,
                    result=result_text,
                )
            elif winner == "reject":
                session.status = "completed"
                session.finished_at = _now()
                session.execution = {
                    "status": "blocked",
                    "reason": "Council rejected the goal.",
                    "dissent": session.dissent,
                }
                result_text = self._format_result(session)
                self._emit(
                    "mission_completed",
                    session,
                    result=result_text,
                    steps=len(session.opinions),
                )
                self._emit("council_completed", session, result=result_text)
            else:
                session.status = "completed"
                session.finished_at = _now()
                result_text = self._format_result(session)
                self._emit(
                    "mission_completed",
                    session,
                    result=result_text,
                    steps=len(session.opinions),
                )
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

    # ── opinion generation ─────────────────────────────────────────────────
    def _parallel_opinions(
        self,
        seats: List[Seat],
        round_name: str,
        session: CouncilSession,
        prior: Optional[List[Opinion]] = None,
    ) -> List[Opinion]:
        prior = prior or []
        out: List[Opinion] = []

        def one(seat: Seat) -> Opinion:
            if self.brain.provider != "offline":
                try:
                    return self._llm_opinion(seat, round_name, session.goal, prior)
                except Exception:
                    pass
            return self._offline_opinion(seat, round_name, session.goal, prior)

        # parallelize briefs/critiques/votes; keep propose parallel too
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(seats) or 1)) as pool:
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
                            ts=_now(),
                        )
                    )
        # stable order by seat list
        order = {s.id: i for i, s in enumerate(seats)}
        out.sort(key=lambda o: order.get(o.seat_id, 99))
        return out

    def _offline_opinion(
        self, seat: Seat, round_name: str, goal: str, prior: List[Opinion]
    ) -> Opinion:
        if round_name == "brief":
            return self._mind.brief(seat, goal)
        if round_name == "propose":
            briefs = [o for o in prior if o.round == "brief"]
            return self._mind.propose(seat, goal, briefs)
        if round_name == "critique":
            props = [o for o in prior if o.round == "propose"]
            return self._mind.critique(seat, goal, props)
        if round_name == "vote":
            return self._mind.vote(seat, goal, prior)
        return self._mind.brief(seat, goal)

    def _llm_opinion(
        self, seat: Seat, round_name: str, goal: str, prior: List[Opinion]
    ) -> Opinion:
        prior_txt = "\n".join(
            f"- [{o.round}/{o.seat_name}] ({o.stance}) {o.summary}"
            for o in prior[-12:]
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
            system="You are a council member. JSON only.",
        )
        # reuse parse_action-like extraction
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
            ts=_now(),
        )

    def _emit_opinion(self, session: CouncilSession, op: Opinion, step: int):
        self._emit(
            "council_opinion",
            session,
            step=step,
            seat=op.seat_id,
            seat_name=op.seat_name,
            round=op.round,
            stance=op.stance,
            summary=op.summary,
            points=op.points,
            risks=op.risks,
            actions=op.actions,
            vote=op.vote,
            weight=op.weight,
        )
        # also map into live trace language the UI already understands
        kind_thought = f"{op.seat_name} · {op.round}: {op.summary}"
        self._emit(
            "thought",
            session,
            step=step,
            thought=kind_thought,
            action=f"council:{op.round}",
            args={"seat": op.seat_id, "stance": op.stance, "vote": op.vote},
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

    # ── directive + execution ──────────────────────────────────────────────
    def _build_directive(
        self, session: CouncilSession, votes: List[Opinion], winner: str
    ) -> dict:
        # Prefer executor/architect/strategist action lists
        ranked_actions: List[str] = []
        for prefer in ("executor", "architect", "strategist", "researcher", "cipher"):
            for o in session.opinions:
                if o.seat_id == prefer and o.actions:
                    for a in o.actions:
                        if a not in ranked_actions:
                            ranked_actions.append(a)
        # critiques may append amendments
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

        summary = (
            f"Council {winner.upper()} on «{session.goal[:80]}» — "
            f"{len(ranked_actions)} action(s), {len(risks)} risk(s) noted."
        )

        # Build a natural-language execution goal the AIAgent understands
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
        }

    def _actions_to_goal(self, original: str, actions: List[str], winner: str) -> str:
        """Turn council actions into a goal the autonomous agent can run."""
        if winner == "reject":
            return f"Do not execute. Explain why the council blocked: {original}"
        # Tool-friendly goals: pass through cleanly (no suffix pollution)
        low = original.lower()
        if any(
            k in low
            for k in (
                "calculate",
                "fibonacci",
                "compute",
                "hide",
                "steganograph",
                "system info",
                "translate",
            )
        ):
            return original.strip()
        if any(
            k in low
            for k in (
                "research",
                "report",
                "build",
                "write",
                "analyze",
                "investigate",
            )
        ):
            return original.strip()

        # Otherwise attach the council's concrete plan as guidance
        useful = [
            a
            for a in actions
            if a
            and not a.lower().startswith("add verify")
            and "sandbox" not in a.lower()
            and "exfiltrat" not in a.lower()
        ]
        if useful:
            steps = "; ".join(useful[:6])
            return f"{original.strip()}. Council plan: {steps}."
        return original

    def _execute_directive(self, session: CouncilSession) -> dict:
        directive = session.directive or {}
        exec_goal = directive.get("exec_goal") or session.goal

        if not self.executor_factory:
            # fallback: just return the directive as the result
            return {
                "status": "no_executor",
                "result": json.dumps(directive, indent=2),
                "goal": exec_goal,
            }

        try:
            agent = self.executor_factory()
            # bind events
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
            f"# ⚖ Council Verdict",
            f"**Goal:** {session.goal}",
            f"**Decision:** {(d.get('decision') or session.status).upper()}",
            f"**Tally:** " + ", ".join(f"{k}={v:.1f}" for k, v in (session.tally or {}).items()),
            "",
            "## Consensus",
            d.get("summary") or session.consensus or "—",
            "",
            "## Action plan",
        ]
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
                lines += ["", "### Agent output", body[:3000]]
        lines += [
            "",
            f"_Seats: {', '.join(session.seats)} · rounds: {', '.join(session.rounds)}_",
        ]
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
                steps = [f"{o.seat_id}:{o.round}" for o in session.opinions[:20]]
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
