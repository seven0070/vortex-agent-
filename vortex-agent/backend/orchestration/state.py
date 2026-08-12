"""
Orchestration State — persistent, durable execution state (LangGraph-style)

State is the single source of truth for a workflow run.
It persists across planning, routing, execution, observation, evaluation, recovery.
Human checkpoints can pause/resume.
"""
from __future__ import annotations
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path

class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNED = "planned"
    ROUTED = "routed"
    RUNNING = "running"
    OBSERVED = "observed"
    EVALUATED = "evaluated"
    SUCCESS = "success"
    FAILED = "failed"
    RECOVERING = "recovering"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

class WorkflowPhase(str, Enum):
    UNDERSTAND = "understand"
    PLAN = "plan"
    DECOMPOSE = "decompose"
    ROUTE = "route"
    EXECUTE = "execute"
    OBSERVE = "observe"
    EVALUATE = "evaluate"
    RECOVER = "recover"
    RESOLVE = "resolve"
    COMPLETE = "complete"

@dataclass
class TaskNode:
    id: str
    goal: str
    description: str = ""
    parent_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None  # bot name or tool
    tool: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 2
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    tokens: int = 0
    latency_ms: int = 0
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self):
        return asdict(self)

@dataclass
class ExecutionTrace:
    id: str
    phase: WorkflowPhase
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class VortexState:
    """
    Central state object for a Vortex run.
    LangGraph inspiration: stateful graph with durable execution, branching, retries, checkpoints.
    """
    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    goal: str = ""
    original_message: str = ""
    phase: WorkflowPhase = WorkflowPhase.UNDERSTAND
    tasks: List[TaskNode] = field(default_factory=list)
    traces: List[ExecutionTrace] = field(default_factory=list)
    memories_used: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    council_deliberation: Optional[Dict[str, Any]] = None
    resolution: Optional[Dict[str, Any]] = None
    governance_decisions: List[Dict[str, Any]] = field(default_factory=list)
    checkpoints: List[str] = field(default_factory=list)
    requires_human: bool = False
    human_feedback: Optional[str] = None
    error: Optional[str] = None
    final_response: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    generation: int = 0

    # --- phase transitions ---
    def transition(self, new_phase: WorkflowPhase, note: str = ""):
        prev = self.phase
        self.phase = new_phase
        self.updated_at = datetime.now().isoformat()
        self.trace(new_phase, f"{prev.value} → {new_phase.value}: {note}")

    def trace(self, phase: WorkflowPhase, message: str, data: dict = None):
        self.traces.append(ExecutionTrace(
            id=f"tr_{uuid.uuid4().hex[:6]}",
            phase=phase,
            message=message,
            data=data or {}
        ))

    def add_task(self, goal: str, description: str = "", parent_id: str = None, tool: str = None, args: dict = None, assigned_to: str = None) -> TaskNode:
        node = TaskNode(
            id=f"task_{uuid.uuid4().hex[:6]}",
            goal=goal,
            description=description,
            parent_id=parent_id,
            tool=tool,
            args=args or {},
            assigned_to=assigned_to,
        )
        self.tasks.append(node)
        return node

    def get_task(self, task_id: str) -> Optional[TaskNode]:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def pending_tasks(self) -> List[TaskNode]:
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    def failed_tasks(self) -> List[TaskNode]:
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "original_message": self.original_message,
            "phase": self.phase.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "traces": [asdict(tr) for tr in self.traces],
            "memories_used": self.memories_used,
            "tool_calls": self.tool_calls,
            "council_deliberation": self.council_deliberation,
            "resolution": self.resolution,
            "governance_decisions": self.governance_decisions,
            "requires_human": self.requires_human,
            "human_feedback": self.human_feedback,
            "error": self.error,
            "final_response": self.final_response,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VortexState":
        tasks = [TaskNode(**t) for t in data.get("tasks", [])]
        traces = [ExecutionTrace(**tr) for tr in data.get("traces", [])]
        return cls(
            run_id=data.get("run_id", f"run_{uuid.uuid4().hex[:8]}"),
            goal=data.get("goal", ""),
            original_message=data.get("original_message", ""),
            phase=WorkflowPhase(data.get("phase", "understand")),
            tasks=tasks,
            traces=traces,
            memories_used=data.get("memories_used", []),
            tool_calls=data.get("tool_calls", []),
            council_deliberation=data.get("council_deliberation"),
            resolution=data.get("resolution"),
            governance_decisions=data.get("governance_decisions", []),
            requires_human=data.get("requires_human", False),
            human_feedback=data.get("human_feedback"),
            error=data.get("error"),
            final_response=data.get("final_response"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
            generation=data.get("generation", 0),
        )

    def summary(self) -> str:
        return (f"run={self.run_id} phase={self.phase.value} tasks={len(self.tasks)} "
                f"pending={len(self.pending_tasks())} failed={len(self.failed_tasks())} "
                f"final={'yes' if self.final_response else 'no'}")

class StateManager:
    """Persists state to disk/SQLite for durable execution (LangGraph durability)."""
    def __init__(self, base_path: Optional[Path] = None):
        from paths import vortex_home
        self.base = base_path or (vortex_home() / "orchestration_state")
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, state: VortexState) -> Path:
        p = self.base / f"{state.run_id}.json"
        p.write_text(json.dumps(state.to_dict(), indent=2))
        return p

    def load(self, run_id: str) -> Optional[VortexState]:
        p = self.base / f"{run_id}.json"
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        return VortexState.from_dict(data)

    def list_recent(self, limit=20) -> List[VortexState]:
        files = sorted(self.base.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]
        out = []
        for f in files:
            try:
                out.append(VortexState.from_dict(json.loads(f.read_text())))
            except:
                pass
        return out
