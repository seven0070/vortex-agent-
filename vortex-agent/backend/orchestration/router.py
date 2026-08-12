"""
Router — decides which agent/tool handles each task (inspired by LangGraph routing + MS Agent Framework handoff patterns)
"""
from __future__ import annotations
from typing import Dict, Any, Optional, List, Tuple
from .state import VortexState, TaskNode, TaskStatus, WorkflowPhase

# council roles mapping
ROLE_MAP = {
    "research": "Researcher",
    "code": "Engineer",
    "coding": "Engineer",
    "secure": "Security",
    "security": "Security",
    "plan": "Planner",
    "critic": "Critic",
    "strategy": "Strategist",
    "verify": "Verifier",
    "general": "Chief",
}

TOOL_MAP = {
    "codeforge": "Engineer",
    "glossopetrae": "Security",
    "steganography": "Security",
    "filesystem": "Engineer",
    "shell": "Engineer",
    "web": "Researcher",
    "browser": "Researcher",
}

class Router:
    def __init__(self, memory=None, skills=None):
        self.memory = memory
        self.skills = skills
        self.routing_history: List[Dict[str, Any]] = []

    def route(self, state: VortexState) -> VortexState:
        state.transition(WorkflowPhase.ROUTE, f"routing {len(state.tasks)} tasks")
        for task in state.tasks:
            if task.status not in (TaskStatus.PLANNED, TaskStatus.PENDING):
                continue
            target, reason = self._route_task(task, state)
            task.assigned_to = target
            task.status = TaskStatus.ROUTED
            self.routing_history.append({
                "task_id": task.id,
                "assigned_to": target,
                "reason": reason,
                "goal": task.goal[:80]
            })
            state.trace(WorkflowPhase.ROUTE, f"task {task.id} → {target} ({reason})", {"task": task.goal[:100], "target": target})
        return state

    def _route_task(self, task: TaskNode, state: VortexState) -> Tuple[str, str]:
        goal_low = task.goal.lower()

        # if task already suggests tool, route to specialist for that tool
        if task.tool and task.tool in TOOL_MAP:
            return TOOL_MAP[task.tool], f"tool {task.tool} affinity"

        # heuristic by keywords
        if any(k in goal_low for k in ("research", "find", "search", "memory", "analyze")):
            return "Researcher", "research keyword"
        if any(k in goal_low for k in ("code", "python", "fibonacci", "benchmark", "calculate", "compute", "run")):
            return "Engineer", "coding keyword"
        if any(k in goal_low for k in ("secure", "hide", "encode", "steg", "encrypt", "translate", "obfuscate")):
            return "Security", "security keyword"
        if any(k in goal_low for k in ("plan", "decompose", "strategy")):
            return "Planner", "planning keyword"
        if any(k in goal_low for k in ("verify", "check", "validate", "test")):
            return "Verifier", "verification keyword"
        if any(k in goal_low for k in ("critic", "review", "evaluate")):
            return "Critic", "critic keyword"

        # memory-based: if task similar to previous success with certain agent, reuse
        if self.memory and hasattr(self.memory, 'recall'):
            try:
                rec = self.memory.recall(task.goal, n=3)
                # if episodic mentions agent
                for r in rec:
                    if r.get("type") == "agent_memory":
                        agent = r.get("agent")
                        if agent:
                            return agent, "memory recall"
            except:
                pass

        # default: Researcher for researchish, Engineer for general
        intent = state.metadata.get("intent", "general")
        if intent in ("research", "general"):
            return "Researcher", f"intent {intent} fallback"
        return "Engineer", "default fallback"

    def handoff(self, from_agent: str, to_agent: str, task: TaskNode, reason: str = "") -> Dict[str, Any]:
        """Microsoft Agent Framework handoff pattern."""
        return {
            "type": "handoff",
            "from": from_agent,
            "to": to_agent,
            "task_id": task.id,
            "reason": reason,
            "timestamp": task.created_at
        }

    def should_use_council(self, state: VortexState) -> bool:
        """Decide if task warrants full council deliberation (layer 4)."""
        # multi-task + complex + high-stakes
        if len(state.tasks) >= 2:
            return True
        if state.metadata.get("strategy") == "swarm_collab":
            return True
        # if any task requires verification or critic
        for t in state.tasks:
            if "verify" in t.goal.lower() or "research and build" in state.goal.lower():
                return True
        return False
