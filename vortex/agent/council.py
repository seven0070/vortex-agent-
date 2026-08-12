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
  ⛰  LifeOS        — danielmiessler/LifeOS       current→ideal state hill-climb
  🔭  Opik          — comet-ml/opik               observability · eval · tracing
  🧬  DSPy          — stanfordnlp/dspy            program LMs · optimize loops
  ☁  Kitesurf      — kitesurf.cloudflare.app     edge · browser · cloud agents
  🧠  Memory        — TencentCloud/TencentDB-Agent-Memory  team memory hub
  🕸  Cognee        — topoteretes/cognee         knowledge-graph memory
  🧩  Multica       — multica-ai/multica         multi-agent issue dispatch
  🚪  Alook         — alookai/alook              rooms for people + agents
  🏢  AgentOffice   — harishkotra/agent-office   pixel office · hire · collab
  📄  OfficeCLI     — iOfficeAI/OfficeCLI        Word/Excel/PPT for agents
  🛠  OpenWork      — different-ai/openwork      open cowork alternative
  🎮  Claw3D        — iamlukethedev/Claw3D       3D engine · sim · OpenClaw
  🏛  AIOffice      — Gaurav2693/ai-office       isometric multi-agent office
  🌊  Ruflo         — ruvnet/ruflo               meta-harness · multiplayer swarms
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
    Seat(
        id="lifeos",
        name="LifeOS",
        title="Life Operating System",
        project="danielmiessler/LifeOS",
        url="https://github.com/danielmiessler/LifeOS",
        mandate=(
            "Hill-climb from Current State to Ideal State. Capture who the user is, "
            "what they care about, and sequence work toward euphoric surprise — "
            "life and work, not just tickets."
        ),
        lens="General harness: Current State → Ideal State with full personal context.",
        toolset="full",
        weight=1.3,
        color="#8b5cf6",
        icon="⛰",
    ),
    Seat(
        id="opik",
        name="Opik",
        title="Observability & Evaluation",
        project="comet-ml/opik",
        url="https://github.com/comet-ml/opik",
        mandate=(
            "Trace every agent step, evaluate outputs, demand metrics and dashboards. "
            "No ship without observability — debug, judge, monitor production runs."
        ),
        lens="LLM ops — traces, evals, prompt management, production-ready signal.",
        toolset="meta",
        weight=1.4,
        color="#06b6d4",
        icon="🔭",
    ),
    Seat(
        id="dspy",
        name="DSPy",
        title="Programmed LM Systems",
        project="stanfordnlp/dspy",
        url="https://github.com/stanfordnlp/dspy",
        mandate=(
            "Program—don't prompt—the system. Compose modular steps, define signatures, "
            "optimize loops with feedback instead of brittle one-shot prompts."
        ),
        lens="Declarative self-improving Python — modules, optimizers, measurable gains.",
        toolset="coding",
        weight=1.4,
        color="#3b82f6",
        icon="🧬",
    ),
    Seat(
        id="kitesurf",
        name="Kitesurf",
        title="Edge & Cloud Agent Runtime",
        project="kitesurf.cloudflare.app",
        url="https://kitesurf.cloudflare.app",
        mandate=(
            "Run agents at the edge: low-latency cloud workers, browser surfaces, "
            "and distributed harnesses. Prefer portable, network-native execution."
        ),
        lens="Cloudflare-edge energy — surf the network, ship where the users are.",
        toolset="web",
        weight=1.1,
        color="#f59e0b",
        icon="☁",
    ),
    Seat(
        id="tencent_memory",
        name="Memory",
        title="Team Memory Hub",
        project="TencentCloud/TencentDB-Agent-Memory",
        url="https://github.com/TencentCloud/TencentDB-Agent-Memory",
        mandate=(
            "Turn conversations, docs, and code into reusable team memory assets: "
            "Chat Memory, Skills, LLM-Wiki, and Code-Graph — governed, shared, "
            "and equipped across agents and frameworks."
        ),
        lens="Agents remember. Humans innovate. — team-level memory that compounds.",
        toolset="memory",
        weight=1.4,
        color="#0ea5e9",
        icon="🧠",
    ),
    Seat(
        id="cognee",
        name="Cognee",
        title="Knowledge-Graph Memory",
        project="topoteretes/cognee",
        url="https://github.com/topoteretes/cognee",
        mandate=(
            "Build persistent long-term memory as a self-hosted knowledge graph. "
            "Ingest any format, connect entities, and let every agent recall with "
            "full relational context across sessions."
        ),
        lens="AI memory platform — graph edges beat flat note dumps.",
        toolset="memory",
        weight=1.4,
        color="#10b981",
        icon="🕸",
    ),
    Seat(
        id="multica",
        name="Multica",
        title="Multi-Agent Dispatch",
        project="multica-ai/multica",
        url="https://github.com/multica-ai/multica",
        mandate=(
            "Treat coding agents like teammates: assign issues across Claude Code, "
            "Codex, Cursor, and many more. Open-source, self-hostable dispatch."
        ),
        lens="Issues → agents as coworkers — route work to the right harness.",
        toolset="delegate",
        weight=1.3,
        color="#6366f1",
        icon="🧩",
    ),
    Seat(
        id="alook",
        name="Alook",
        title="People + Agent Rooms",
        project="alookai/alook",
        url="https://github.com/alookai/alook",
        mandate=(
            "Design rooms where humans and agents share context, presence, and work. "
            "Collaboration UX first — not a black-box batch job."
        ),
        lens="Rooms for people and agents — presence, threads, shared state.",
        toolset="core",
        weight=1.1,
        color="#ec4899",
        icon="🚪",
    ),
    Seat(
        id="agent_office",
        name="AgentOffice",
        title="Living Agent Workplace",
        project="harishkotra/agent-office",
        url="https://github.com/harishkotra/agent-office",
        mandate=(
            "Simulate a living office: agents walk, think, hire, assign tasks, "
            "execute code, search the web, and grow the team with persistent memory."
        ),
        lens="Pixel-office energy — watch the swarm work in real time.",
        toolset="full",
        weight=1.2,
        color="#a855f7",
        icon="🏢",
    ),
    Seat(
        id="officecli",
        name="OfficeCLI",
        title="Office Documents for Agents",
        project="iOfficeAI/OfficeCLI",
        url="https://github.com/iOfficeAI/OfficeCLI",
        mandate=(
            "Deliver real Office artifacts: read/edit/automate Word, Excel, PowerPoint "
            "without installing Microsoft Office. Single binary, agent-native."
        ),
        lens="Docs are the product — ship .docx/.xlsx/.pptx, not only markdown.",
        toolset="files",
        weight=1.3,
        color="#2563eb",
        icon="📄",
    ),
    Seat(
        id="openwork",
        name="OpenWork",
        title="Open Cowork Harness",
        project="different-ai/openwork",
        url="https://github.com/different-ai/openwork",
        mandate=(
            "Open-source alternative to closed cowork agents. Practical desktop/work "
            "automation powered by open harnesses — finish real workplace tasks."
        ),
        lens="Cowork without lock-in — open stack, finished work.",
        toolset="full",
        weight=1.2,
        color="#14b8a6",
        icon="🛠",
    ),
    Seat(
        id="claw3d",
        name="Claw3D",
        title="3D Engine & Simulation",
        project="iamlukethedev/Claw3D",
        url="https://github.com/iamlukethedev/Claw3D",
        mandate=(
            "Own spatial/sim work: games, simulations, high-performance 3D apps "
            "on an OpenClaw-class engine. When the world is 3D, think in scenes."
        ),
        lens="3D runtime — simulations and interactive worlds, not just text.",
        toolset="coding",
        weight=1.1,
        color="#f43f5e",
        icon="🎮",
    ),
    Seat(
        id="ai_office",
        name="AIOffice",
        title="Isometric Multi-Agent Office",
        project="Gaurav2693/ai-office",
        url="https://github.com/Gaurav2693/ai-office",
        mandate=(
            "Coordinate a miniature office of agents that walk, talk, and hold meetings. "
            "Make multi-agent coordination visible and legible."
        ),
        lens="Isometric office sim — meetings, desks, visible collaboration.",
        toolset="core",
        weight=1.0,
        color="#eab308",
        icon="🏛",
    ),
    Seat(
        id="ruflo",
        name="Ruflo",
        title="Agent Meta-Harness",
        project="ruvnet/ruflo",
        url="https://github.com/ruvnet/ruflo",
        mandate=(
            "Deploy intelligent multi-player swarms, coordinate autonomous workflows, "
            "and weave adaptive memory + RAG across Claude Code / Codex / Hermes and more."
        ),
        lens="The original agent meta-harness — swarms, workflows, self-learning.",
        toolset="full",
        weight=1.5,
        color="#06b6d4",
        icon="🌊",
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
    chamber: Dict[str, Any] = field(default_factory=dict)
    dissent: List[str] = field(default_factory=list)
    created_at: str = ""
    finished_at: str = ""
    auto_execute: bool = True
    max_rounds: int = 3
    use_chamber: bool = True

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
            "chamber": self.chamber,
            "dissent": self.dissent,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "auto_execute": self.auto_execute,
            "use_chamber": self.use_chamber,
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

        elif seat.id == "lifeos":
            points = [
                "Name Current State vs Ideal State for this goal.",
                "Sequence the smallest hill-climb that moves life/work forward.",
                "Capture personal/context constraints before optimizing tactics.",
            ]
            actions = [
                "Define current_state + ideal_state",
                "Pick one high-leverage next step",
                "write_file plans/lifeos-step.md",
                "memory_store the decision",
            ]
            stance = "support"
            if any(k in g for k in ("calculate", "fib", "math")):
                actions = ["calculator or execute_code", "Record result as a milestone", "Finish"]

        elif seat.id == "opik":
            points = [
                "Every step must be traceable — thought, tool, observation.",
                "Define success metrics before execution; evaluate after.",
                "No silent failures — log status and produce an eval note.",
            ]
            actions = [
                "Instrument the run (trace each tool call)",
                "Define eval criteria",
                "memory_store eval summary",
                "Reject ship without verify",
            ]
            stance = "amend"
            risks = ["Unmeasured runs can't improve — demand an eval signal."]

        elif seat.id == "dspy":
            points = [
                "Treat the plan as a modular program, not a prompt blob.",
                "Define input/output signatures per step; optimize with feedback.",
                "Prefer compose → measure → refine over one-shot generation.",
            ]
            actions = [
                "Decompose into typed steps (signature per step)",
                "execute_code / tools per module",
                "Score output vs criteria",
                "Iterate once if score fails",
            ]
            stance = "support"
            if any(k in g for k in ("calculate", "fib", "math")):
                actions = ["calculator module", "assert numeric result", "Finish"]

        elif seat.id == "kitesurf":
            points = [
                "Prefer network-native paths: search, fetch, edge-friendly artifacts.",
                "Keep the harness portable — workspace files beat local-only state.",
                "When research is needed, ride the open web first.",
            ]
            actions = ["web_search", "http_fetch top hit if URL exists", "write_file edge-ready report"]
            stance = "support" if any(k in g for k in ("research", "web", "cloud", "deploy", "browser")) else "amend"

        elif seat.id == "tencent_memory":
            points = [
                "Promote this run into team assets: chat memory, skill, wiki, or code-graph.",
                "Memory must be governed and shareable across agents — not a private dump.",
                "Equip the next agent with what this session learns.",
            ]
            actions = [
                "memory_store structured findings",
                "Save a skill if the path works",
                "Tag assets for team reuse",
            ]
            stance = "support"
            if any(k in g for k in ("remember", "memory", "recall", "knowledge")):
                stance = "support"
                actions = ["memory_recall related notes", "memory_store update", "Finish"]

        elif seat.id == "cognee":
            points = [
                "Ingest results into a knowledge graph — entities + relations, not only prose.",
                "Cross-session recall should traverse edges (who/what/why linked).",
                "Self-hosted memory beats disposable context windows.",
            ]
            actions = [
                "memory_store with entity-rich text",
                "memory_recall before acting on related goals",
                "write_file knowledge/<slug>.md graph notes",
            ]
            stance = "support"
            if any(k in g for k in ("research", "analyze", "report", "knowledge", "memory")):
                actions = [
                    "web_search / gather sources",
                    "memory_store linked findings",
                    "write_file knowledge graph summary",
                ]

        elif seat.id == "multica":
            points = [
                "Split the goal into assignable issues for specialist agents.",
                "Route coding work to the right harness — don't monopolize one bot.",
                "Self-host dispatch; keep ownership of the queue.",
            ]
            actions = [
                "Decompose into issues/tasks",
                "delegate_task to specialists",
                "Merge results into one deliverable",
            ]
            stance = "support"
            if any(k in g for k in ("calculate", "fib", "math")):
                actions = ["calculator or execute_code", "Print the number", "Finish"]

        elif seat.id == "alook":
            points = [
                "This should feel like a shared room — clear presence and handoffs.",
                "Surface progress so a human can join mid-flight.",
            ]
            actions = ["Log shared plan in workspace", "Keep steps human-readable"]
            stance = "amend"
            risks = ["Solo black-box runs freeze out collaborators."]

        elif seat.id == "agent_office":
            points = [
                "Staff the goal like an office: roles, desks, hire helpers if needed.",
                "Agents should assign tasks to each other and keep memory across sessions.",
            ]
            actions = [
                "Assign roles (research/build/review)",
                "delegate_task where parallel",
                "memory_store office log",
            ]
            stance = "support"

        elif seat.id == "officecli":
            points = [
                "If the outcome is a document, ship a real Office artifact path.",
                "Word/Excel/PPT beats chat walls for workplace deliverables.",
            ]
            actions = [
                "write_file deliverable (md/csv as stand-in)",
                "Structure tables/sections cleanly",
                "Name the final file path",
            ]
            stance = "support" if any(
                k in g for k in ("report", "doc", "spreadsheet", "slide", "office", "write")
            ) else "amend"

        elif seat.id == "openwork":
            points = [
                "Cowork without lock-in — finish the workplace task openly.",
                "Prefer practical automation over demo fluff.",
            ]
            actions = ["Name the workplace outcome", "Execute with tools", "Return finished path"]
            stance = "support"

        elif seat.id == "claw3d":
            points = [
                "If the problem is spatial/sim/interactive, think scenes and runtime.",
                "Otherwise stay out of the way and support code/sim scaffolding.",
            ]
            actions = ["execute_code scaffold if needed", "write_file sim/plan notes"]
            stance = "support" if any(
                k in g for k in ("3d", "game", "sim", "scene", "render", "physics")
            ) else "amend"

        elif seat.id == "ai_office":
            points = [
                "Make multi-agent coordination visible — meetings, owners, desks.",
                "Legible swarm > invisible fan-out.",
            ]
            actions = ["Publish a meeting agenda", "Assign owners per step", "Share status board file"]
            stance = "amend"

        elif seat.id == "ruflo":
            points = [
                "Meta-harness the swarm: adaptive memory, RAG, multi-player workflows.",
                "Coordinate across harnesses (Claude/Codex/Hermes-class) as one system.",
                "Self-learning loops beat one-shot runs.",
            ]
            actions = [
                "Spin a multi-agent workflow",
                "delegate_task parallel workstreams",
                "memory_store + skill promotion",
                "Verify merged output",
            ]
            stance = "support"

        else:  # notebook
            points = [
                "Ground claims in search/fetch evidence.",
                "Structure findings before anyone builds on them.",
            ]
            actions = ["web_search", "http_fetch if URL exists", "write_file reports/<slug>.md"]
            stance = "support" if any(k in g for k in ("research", "report", "what is", "explain", "analyze")) else "amend"

        # Goal-specific overrides shared across seats
        if any(k in g for k in ("calculate", "fibonacci", "math", "compute")):
            if seat.id in (
                "grok", "zero", "openworker", "hermes", "dspy", "lifeos",
                "multica", "openwork", "ruflo",
            ):
                actions = ["calculator or execute_code", "Print the number", "Finish"]
                stance = "support"
        if any(k in g for k in ("hide", "steg", "secret", "encrypt")):
            if seat.id in (
                "zero", "hermes", "prime", "openworker", "opik",
                "tencent_memory", "openwork",
            ):
                actions = ["steganography encode", "Return encoded cover text"]
                stance = "support"
        if any(k in g for k in ("hack", "exploit", "malware", "steal", "weapon", "ddos", "phish")):
            if seat.id in (
                "prime", "hermes", "buzz", "qm", "opik", "lifeos",
                "tencent_memory", "cognee", "alook", "ruflo", "openwork",
            ):
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

        # Synthesizers merge a spine from all briefs
        if seat.id in ("openworker", "hermes", "zero", "lifeos", "dspy", "ruflo", "openwork", "multica"):
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
        if seat.id == "kitesurf" and not actions:
            actions = ["web_search", "http_fetch", "write_file reports/edge-brief.md"]
        if seat.id == "opik":
            base = actions or ["Execute core path"]
            actions = base + ["Trace each step", "Eval against criteria", "memory_store eval"]
            seen = set()
            actions = [a for a in actions if not (a in seen or seen.add(a))]
        if seat.id == "dspy" and not actions:
            actions = [
                "Define step signatures",
                "Run modules via tools",
                "Score + one refine pass",
            ]
        if seat.id == "lifeos" and not actions:
            actions = [
                "current_state → ideal_state note",
                "One hill-climb action",
                "write_file plans/next.md",
            ]
        if seat.id == "tencent_memory":
            base = actions or ["Execute core path"]
            actions = base + [
                "memory_store team asset",
                "Promote path to skill if reusable",
            ]
            seen = set()
            actions = [a for a in actions if not (a in seen or seen.add(a))]
        if seat.id == "cognee":
            base = actions or ["Gather inputs"]
            actions = base + [
                "memory_store entity-linked notes",
                "memory_recall related graph context",
                "write_file knowledge summary",
            ]
            seen = set()
            actions = [a for a in actions if not (a in seen or seen.add(a))]
        if seat.id == "multica" and not actions:
            actions = ["Split into issues", "delegate_task specialists", "Merge deliverable"]
        if seat.id == "alook" and not actions:
            actions = ["Publish shared room plan", "Human-readable status file"]
        if seat.id == "agent_office" and not actions:
            actions = ["Staff roles", "delegate_task", "memory_store office log"]
        if seat.id == "officecli" and not actions:
            actions = ["write_file office-style deliverable", "Structure sections/tables"]
        if seat.id == "openwork" and not actions:
            actions = ["Define workplace outcome", "Execute tools", "Return finished path"]
        if seat.id == "claw3d" and not actions:
            actions = ["Scaffold sim/notes", "execute_code if needed"]
        if seat.id == "ai_office" and not actions:
            actions = ["Meeting agenda", "Owner board", "Status file"]
        if seat.id == "ruflo":
            base = actions or ["Coordinate swarm"]
            actions = base + [
                "delegate_task parallel streams",
                "memory_store workflow state",
                "Verify merged output",
            ]
            seen = set()
            actions = [a for a in actions if not (a in seen or seen.add(a))]
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

        elif seat.id == "opik":
            points = ["Where are the traces and eval criteria?"]
            risks = ["Untraced execution is un-debuggable in production."]
            actions = ["Require step traces", "Write eval note after run"]
            stance = "amend"

        elif seat.id == "dspy":
            points = ["Is the plan modular with clear I/O per step?"]
            risks = ["Monolithic one-shot prompts won't optimize."]
            actions = ["Split into signatures", "Add a score-and-refine loop"]
            stance = "amend"

        elif seat.id == "lifeos":
            points = ["Does this move Current State toward Ideal State, or just busywork?"]
            risks = ["Tactical thrash without a north-star outcome."]
            actions = ["Re-state ideal outcome", "Keep only high-leverage steps"]
            stance = "amend"

        elif seat.id == "kitesurf":
            points = ["Can this run at the edge / over the network cleanly?"]
            risks = ["Local-only assumptions break cloud portability."]
            stance = "support"

        elif seat.id == "tencent_memory":
            points = ["Will this session leave reusable team memory assets?"]
            risks = ["Knowledge dies in chat if not stored as chat/skill/wiki/code-graph."]
            actions = ["memory_store outcome", "skill_view / save learned skill"]
            stance = "amend"

        elif seat.id == "cognee":
            points = ["Are findings linked as a graph (entities + relations)?"]
            risks = ["Flat notes without edges block multi-hop recall later."]
            actions = ["memory_store entity-rich text", "memory_recall before next related task"]
            stance = "amend"

        elif seat.id == "multica":
            points = ["Is work split into assignable issues for multiple harnesses?"]
            risks = ["Single-threaded ownership bottlenecks the swarm."]
            actions = ["Issue-ize remaining steps", "delegate_task"]
            stance = "amend"

        elif seat.id == "alook":
            points = ["Could a human walk into this room and understand state in 30s?"]
            risks = ["Opaque agent chatter kills collaboration."]
            actions = ["Write a shared status note"]
            stance = "amend"

        elif seat.id == "agent_office":
            points = ["Who sits which desk — are roles and hires explicit?"]
            risks = ["Unowned tasks stall the office floor."]
            stance = "support"

        elif seat.id == "officecli":
            points = ["Is there a concrete document artifact path?"]
            risks = ["Chat-only deliverables don't survive workplace handoff."]
            actions = ["write_file final deliverable"]
            stance = "amend"

        elif seat.id == "openwork":
            points = ["Does this finish a real workplace task without vendor lock-in?"]
            stance = "support"

        elif seat.id == "claw3d":
            points = ["Spatial/sim needs called out, or stay lean on text path."]
            stance = "support"

        elif seat.id == "ai_office":
            points = ["Is multi-agent work visible as a meeting/board?"]
            actions = ["Publish owner board"]
            stance = "amend"

        elif seat.id == "ruflo":
            points = ["Meta-harness check: parallel streams, memory, verify merge."]
            risks = ["Swarms without merge/verify thrash."]
            actions = ["Parallelize", "Merge", "Verify"]
            stance = "amend"

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

        # harm veto from quality/collab/obs/memory seats
        if any(k in g for k in ("hack", "exploit", "malware", "steal", "weapon", "ddos", "phish")):
            if seat.id in (
                "prime", "hermes", "buzz", "qm", "openworker", "opik",
                "lifeos", "tencent_memory", "cognee", "alook", "ruflo",
                "openwork", "multica",
            ):
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

        if gate_oppose and seat.id in (
            "prime", "hermes", "buzz", "qm", "openworker", "zero",
            "opik", "lifeos", "tencent_memory", "cognee",
            "alook", "ruflo", "openwork", "multica",
        ):
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
        elif seat.id == "opik":
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "eval" in text or "trace" in text or "verif" in text or "memory_store" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE — observability path present."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — need traces + eval."
        elif seat.id == "dspy":
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "module" in text or "signature" in text or "step" in text or "score" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE — modular program path."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — modularize the plan."
        elif seat.id == "tencent_memory":
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "memory_store" in text or "skill" in text or "wiki" in text or "graph" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE — team memory path present."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — store team memory assets."
        elif seat.id == "cognee":
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "memory" in text or "graph" in text or "entity" in text or "recall" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE — knowledge-graph path present."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — link findings in graph memory."
        elif seat.id == "ruflo":
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "delegate" in text or "swarm" in text or "verif" in text or "memory" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE — meta-harness path present."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — add swarm + verify merge."
        elif seat.id == "multica":
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "delegate" in text or "issue" in text or "split" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE — multi-agent dispatch path."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — issue-ize and dispatch."
        elif seat.id == "officecli":
            text = " ".join(o.summary + " ".join(o.actions) for o in history).lower()
            if "write_file" in text or "report" in text or "deliverable" in text:
                vote, stance = "approve", "support"
                summary = f"{seat.name} votes APPROVE — document artifact path."
            else:
                vote, stance = "amend", "amend"
                summary = f"{seat.name} votes AMEND — produce an office artifact."
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
        for prefer in (
            "ruflo", "openworker", "hermes", "zero", "grok", "dspy", "lifeos",
            "multica", "openwork", "notebook", "eve", "kitesurf", "opik",
            "tencent_memory", "cognee", "officecli", "agent_office",
            "ai_office", "alook", "claw3d", "prime",
        ):
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
        seat_worker_factory: Optional[Callable[..., Any]] = None,
        use_chamber: bool = True,
    ):
        self.session_db = session_db
        self.vector = vector
        self.skills = skills
        self.memory_provider = memory_provider
        self.brain = brain or LLMBrain()
        self.event_cb = event_cb
        self.seats = {s.id: s for s in (seats or DEFAULT_SEATS)}
        self.executor_factory = executor_factory
        # seat_worker_factory(toolset=, role=, blocked=) -> AIAgent
        self.seat_worker_factory = seat_worker_factory
        self.use_chamber = use_chamber
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
        use_chamber: Optional[bool] = None,
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
            use_chamber=self.use_chamber if use_chamber is None else bool(use_chamber),
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
                if s.id in (
                    "hermes", "zero", "grok", "openworker", "notebook", "eve",
                    "prime", "odysseus", "lifeos", "dspy", "kitesurf", "opik",
                    "tencent_memory", "cognee", "ruflo", "multica", "openwork",
                    "officecli", "agent_office", "alook", "ai_office", "claw3d",
                )
            ] or seats[:8]
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

            # 3 CRITIQUE — quality + collab + evidence + eval
            critics = [
                s for s in seats
                if s.id in (
                    "prime", "hermes", "buzz", "qm", "eve", "notebook",
                    "openworker", "opik", "dspy", "lifeos", "kitesurf",
                    "tencent_memory", "cognee", "ruflo", "multica", "alook",
                    "officecli", "openwork", "agent_office", "ai_office",
                )
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
                self._emit(
                    "council_executing",
                    session,
                    message="Chamber + chief executing council directive",
                )
                session.execution = self._execute_directive(session)
                session.chamber = {
                    k: session.execution.get(k)
                    for k in (
                        "mode",
                        "workers",
                        "worker_count",
                        "completed",
                        "failed",
                        "chamber_dir",
                        "verdict_path",
                        "final_path",
                        "summary",
                    )
                    if k in (session.execution or {})
                }
                # chamber is part of the execution pipeline
                if "chamber" not in session.rounds:
                    session.rounds.append("chamber")
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
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(24, len(seats) or 1)) as pool:
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
            "ruflo", "openworker", "hermes", "zero", "grok", "dspy", "lifeos",
            "multica", "openwork", "notebook", "eve", "kitesurf", "odysseus",
            "opik", "tencent_memory", "cognee", "officecli", "agent_office",
            "ai_office", "alook", "claw3d", "prime", "qm", "buzz",
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

        # ── Chamber path: real parallel seat agents ─────────────────────
        if session.use_chamber and self.seat_worker_factory is not None:
            try:
                from vortex.agent.chamber import CouncilChamber

                chamber = CouncilChamber(
                    executor_factory=self.seat_worker_factory,
                    event_cb=self.event_cb,
                )
                return chamber.run(
                    council_id=session.id,
                    goal=session.goal,
                    seats=self.seats,
                    seat_ids=session.seats,
                    directive=directive,
                    chief_factory=self.executor_factory,
                )
            except Exception as e:
                # fall through to single-chief path
                fallback_err = str(e)
        else:
            fallback_err = None

        if not self.executor_factory:
            return {
                "status": "no_executor",
                "result": json.dumps(directive, indent=2),
                "goal": exec_goal,
                "chamber_error": fallback_err,
            }
        try:
            agent = self.executor_factory()
            agent.event_cb = self.event_cb
            result = agent.run(exec_goal, background=False, max_steps=12)
            out = {
                "status": result.get("status"),
                "mode": "chief_only",
                "mission_id": result.get("id"),
                "result": result.get("result") or result.get("error") or "",
                "steps": result.get("step_count"),
                "goal": exec_goal,
            }
            if fallback_err:
                out["chamber_error"] = fallback_err
            return out
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "goal": exec_goal,
                "chamber_error": fallback_err,
            }

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
        elif ex.get("mode") == "chamber":
            lines.append(
                f"Mode: **chamber** · workers={ex.get('worker_count', 0)} "
                f"({ex.get('completed', 0)} ok / {ex.get('failed', 0)} failed)"
            )
            if ex.get("chamber_dir"):
                lines.append(f"Chamber: `{ex.get('chamber_dir')}/`")
            if ex.get("final_path"):
                lines.append(f"Final: `{ex.get('final_path')}`")
            workers = ex.get("workers") or []
            if workers:
                lines += ["", "### Seat workers"]
                for w in workers:
                    flag = "✅" if w.get("status") == "completed" else "❌"
                    lines.append(
                        f"- {flag} **{w.get('seat_name')}** (`{w.get('seat_id')}`) "
                        f"— {w.get('status')} · {w.get('steps', 0)} steps"
                        + (f" · `{w.get('artifact')}`" if w.get("artifact") else "")
                    )
            body = (ex.get("result") or "").strip()
            if body:
                lines += ["", "### Chamber verdict", body[:4000]]
        else:
            lines.append(
                f"Status: {ex.get('status', 'n/a')} · mission={ex.get('mission_id', '—')}"
            )
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
