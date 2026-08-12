"""
Vortex Graph — state machine orchestrating Goal → Understand → Plan → Decompose → Route → Execute → Observe → Evaluate → Recover/Continue → Resolve

LangGraph inspiration: stateful graph with durable execution, branching, retries, human checkpoints.

Each node is a function that takes state and returns state.
Graph has edges defining transitions.
"""
from __future__ import annotations
from typing import Dict, Any, Callable, List, Optional
from .state import VortexState, WorkflowPhase, TaskStatus, StateManager
from .planner import Planner
from .router import Router
from .executor import Executor
from .recovery import RecoveryEngine

NodeFunc = Callable[[VortexState], VortexState]

class VortexGraph:
    """
    Stateful graph executor.

    Default graph:
      understand → plan → decompose → route → execute → observe → evaluate → (recover → execute)? → resolve → complete
    Branching:
      - if evaluate needs_recovery and retries left → recover → route → execute
      - if governance escalates → human checkpoint node
      - resolution can loop back to planning if Resolver says none good enough
    """
    def __init__(self, planner: Planner, router: Router, executor: Executor, recovery: RecoveryEngine,
                 resolver=None, council=None, state_manager: StateManager = None,
                 governance=None, max_loops=3):
        self.planner = planner
        self.router = router
        self.executor = executor
        self.recovery = recovery
        self.resolver = resolver
        self.council = council
        self.governance = governance
        self.state_manager = state_manager or StateManager()
        self.max_loops = max_loops
        self.nodes: Dict[str, NodeFunc] = {}
        self._build_nodes()

    def _build_nodes(self):
        self.nodes["understand"] = self._node_understand
        self.nodes["plan"] = self._node_plan
        self.nodes["decompose"] = self._node_decompose
        self.nodes["route"] = self._node_route
        self.nodes["execute"] = self._node_execute
        self.nodes["observe"] = self._node_observe
        self.nodes["evaluate"] = self._node_evaluate
        self.nodes["recover"] = self._node_recover
        self.nodes["council"] = self._node_council
        self.nodes["resolve"] = self._node_resolve
        self.nodes["complete"] = self._node_complete
        self.nodes["human_checkpoint"] = self._node_human_checkpoint

    # ---- node implementations ----
    def _node_understand(self, state: VortexState) -> VortexState:
        return self.planner.understand(state)

    def _node_plan(self, state: VortexState) -> VortexState:
        return self.planner.plan(state)

    def _node_decompose(self, state: VortexState) -> VortexState:
        return self.planner.decompose(state)

    def _node_route(self, state: VortexState) -> VortexState:
        return self.router.route(state)

    def _node_execute(self, state: VortexState) -> VortexState:
        return self.executor.execute(state)

    def _node_observe(self, state: VortexState) -> VortexState:
        return self.recovery.observe(state)

    def _node_evaluate(self, state: VortexState) -> VortexState:
        return self.recovery.evaluate(state)

    def _node_recover(self, state: VortexState) -> VortexState:
        new_state, recovered = self.recovery.recover(state)
        new_state.metadata["recovered"] = recovered
        return new_state

    def _node_council(self, state: VortexState) -> VortexState:
        """Council deliberation if warranted."""
        if not self.council:
            state.trace(WorkflowPhase.RESOLVE, "no council, skipping")
            return state
        if not self.router.should_use_council(state):
            state.trace(WorkflowPhase.RESOLVE, "council not needed for simple task")
            return state
        try:
            deliberation = self.council.deliberate(state)
            state.council_deliberation = deliberation
            state.trace(WorkflowPhase.RESOLVE, f"council deliberation: {deliberation.get('decision')}")
        except Exception as e:
            state.trace(WorkflowPhase.RESOLVE, f"council failed: {e}")
        return state

    def _node_resolve(self, state: VortexState) -> VortexState:
        state.transition(WorkflowPhase.RESOLVE, "resolving candidates")
        if self.resolver:
            try:
                # collect candidates from task results
                candidates = []
                for t in state.tasks:
                    if t.status == TaskStatus.SUCCESS and t.result:
                        candidates.append({
                            "task_id": t.id,
                            "result": t.result,
                            "confidence": t.confidence,
                            "assigned_to": t.assigned_to,
                            "latency_ms": t.latency_ms,
                            "evidence": t.evidence or [str(t.result)[:200]]
                        })
                if not candidates and state.tasks:
                    # fallback: use task list as candidates
                    candidates = [{"result": t.result, "confidence": 0.5} for t in state.tasks if t.result]

                # also include council output
                if state.council_deliberation:
                    candidates.append({
                        "task_id": "council",
                        "result": state.council_deliberation.get("final", ""),
                        "confidence": state.council_deliberation.get("confidence", 0.7),
                        "assigned_to": "council"
                    })

                resolution = self.resolver.resolve(candidates, goal=state.goal, state=state)
                state.resolution = resolution
                state.final_response = resolution.get("selected", {}).get("result") or resolution.get("final_response") or ""

                # if resolver says none good enough, loop back to planning
                if resolution.get("action") == "replan":
                    state.metadata["replan_requested"] = True
                    state.trace(WorkflowPhase.RESOLVE, "resolver requested replan → looping to plan")

            except Exception as e:
                state.trace(WorkflowPhase.RESOLVE, f"resolver error: {e}")
                state.final_response = ""
        else:
            # simple fallback: merge task results
            parts = []
            for t in state.tasks:
                if t.result:
                    parts.append(str(t.result))
            state.final_response = "\n\n".join(parts)[:2000]
        return state

    def _node_complete(self, state: VortexState) -> VortexState:
        state.transition(WorkflowPhase.COMPLETE, "complete")
        if not state.final_response:
            # synthesis fallback
            results = [str(t.result) for t in state.tasks if t.result]
            state.final_response = "\n\n".join(results)[:2000] if results else "Task completed (no output)"
        state.trace(WorkflowPhase.COMPLETE, f"final len={len(state.final_response)}")
        return state

    def _node_human_checkpoint(self, state: VortexState) -> VortexState:
        state.requires_human = True
        state.trace(WorkflowPhase.EVALUATE, "human checkpoint triggered")
        return state

    # ---- execution loop ----
    def run(self, goal: str, original_message: str = None, generation: int = 0, max_loops: int = None) -> VortexState:
        max_loops = max_loops or self.max_loops
        state = VortexState(goal=goal, original_message=original_message or goal, generation=generation)

        # durable execution sequence with branching
        sequence = ["understand", "plan", "decompose", "route", "execute", "observe", "evaluate"]

        for node_name in sequence:
            state = self.nodes[node_name](state)
            self.state_manager.save(state)
            if state.requires_human:
                state = self.nodes["human_checkpoint"](state)
                self.state_manager.save(state)
                break

        # Check if recovery needed (branch)
        loops = 0
        while state.metadata.get("needs_recovery") and loops < max_loops:
            loops += 1
            failed = state.failed_tasks()
            if not failed:
                break
            # try recover
            state = self.nodes["recover"](state)
            self.state_manager.save(state)
            if state.requires_human:
                state = self.nodes["human_checkpoint"](state)
                break
            if not state.metadata.get("recovered"):
                # still failed, but proceed to council/resolve anyway
                break
            # re-route and re-execute pending
            state = self.nodes["route"](state)
            state = self.nodes["execute"](state)
            state = self.nodes["observe"](state)
            state = self.nodes["evaluate"](state)
            self.state_manager.save(state)

        # council (if needed) then resolve
        state = self.nodes["council"](state)
        self.state_manager.save(state)

        state = self.nodes["resolve"](state)
        self.state_manager.save(state)

        # if resolver requested replan, loop once more
        if state.metadata.get("replan_requested") and loops < max_loops:
            state.trace(WorkflowPhase.PLAN, "replanning after resolver rejection")
            # clear tasks and replan
            state.tasks = []
            state.metadata["replan_requested"] = False
            state = self.nodes["plan"](state)
            state = self.nodes["decompose"](state)
            state = self.nodes["route"](state)
            state = self.nodes["execute"](state)
            state = self.nodes["council"](state)
            state = self.nodes["resolve"](state)

        state = self.nodes["complete"](state)
        self.state_manager.save(state)
        return state

def create_default_graph(agent=None, memory=None, tools=None, governance=None, resolver=None, council=None, observability=None) -> VortexGraph:
    """Factory for default orchestrated graph."""
    from .state import StateManager
    planner = Planner(memory=memory)
    router = Router(memory=memory)
    executor = Executor(agent=agent, tool_registry=tools, memory=memory, observability=observability)
    recovery = RecoveryEngine(memory=memory, governance=governance)
    state_manager = StateManager()
    graph = VortexGraph(
        planner=planner,
        router=router,
        executor=executor,
        recovery=recovery,
        resolver=resolver,
        council=council,
        state_manager=state_manager,
        governance=governance
    )
    return graph
