"""
Recovery Engine — when tasks fail: Observe → Evaluate → Recover / Continue

Implements:
- error classification
- retry with mutation (like existing RSI retry_tool)
- replan suggestion to planner
- fallback to human checkpoint if unrecoverable
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from .state import VortexState, TaskNode, TaskStatus, WorkflowPhase

class RecoveryEngine:
    def __init__(self, memory=None, governance=None):
        self.memory = memory
        self.governance = governance

    def observe(self, state: VortexState) -> VortexState:
        state.transition(WorkflowPhase.OBSERVE, "observing execution results")
        failed = state.failed_tasks()
        success = [t for t in state.tasks if t.status == TaskStatus.SUCCESS]

        state.trace(WorkflowPhase.OBSERVE,
                    f"observed {len(success)} success, {len(failed)} failed",
                    {"success": len(success), "failed": len(failed)})

        # store observations in episodic memory if available
        if self.memory:
            for t in failed:
                try:
                    self.memory.episodic.remember_event(
                        f"FAIL task {t.id}: {t.goal} error={t.error}",
                        kind="failure",
                        meta={"task_id": t.id, "error": t.error}
                    )
                except:
                    pass
        return state

    def evaluate(self, state: VortexState) -> VortexState:
        state.transition(WorkflowPhase.EVALUATE, "evaluating quality")
        # evaluate each task confidence threshold
        low_conf = [t for t in state.tasks if t.status == TaskStatus.SUCCESS and t.confidence < 0.4]
        failed = state.failed_tasks()

        needs_recovery = (len(failed) > 0) or (len(low_conf) > 0)
        state.metadata["needs_recovery"] = needs_recovery
        state.metadata["low_conf_tasks"] = [t.id for t in low_conf]
        state.metadata["failed_tasks"] = [t.id for t in failed]

        state.trace(WorkflowPhase.EVALUATE,
                    f"needs_recovery={needs_recovery} low_conf={len(low_conf)} failed={len(failed)}")
        return state

    def recover(self, state: VortexState) -> Tuple[VortexState, bool]:
        """
        Attempt recovery. Returns (state, recovered_bool)
        If unrecoverable, sets human checkpoint.
        """
        state.transition(WorkflowPhase.RECOVER, "recovering")
        failed = state.failed_tasks()

        # try tool-level retry mutation (RSI style)
        recovered_tasks = []
        for task in failed:
            mutated = self._mutate_task(task)
            if mutated:
                recovered_tasks.append(mutated)
                state.trace(WorkflowPhase.RECOVER, f"mutated task {task.id}: {mutated}")

        # if we mutated some, reset them to pending for re-execution
        if recovered_tasks:
            for task in failed:
                if task.retries < task.max_retries:
                    task.status = TaskStatus.PENDING
                    task.error = None
                    task.retries += 1
            state.trace(WorkflowPhase.RECOVER, f"set {len(recovered_tasks)} tasks to retry")
            return state, True

        # if still failed and has governance, ask governance if human needed
        if self.governance:
            try:
                decision = self.governance.evaluate(task="recovery", context={"failed_count": len(failed)})
                if decision.get("action") == "ESCALATE":
                    state.requires_human = True
                    state.trace(WorkflowPhase.RECOVER, "escalated to human checkpoint via governance")
                    return state, False
            except:
                pass

        # if failures persist, mark unresolved but allow resolve to decide
        if failed:
            state.trace(WorkflowPhase.RECOVER, f"{len(failed)} failures unrecovered, proceeding to resolution")
            return state, False

        return state, True

    def _mutate_task(self, task: TaskNode) -> Optional[Dict[str, Any]]:
        """Mutate args similar to RSI retry_tool."""
        if task.tool == "codeforge":
            code = task.args.get("code", "")
            err = (task.error or "").lower()
            if "syntax" in err and "print" not in code:
                return {"code": f"print({code.strip()})"}
            if not code.strip():
                # try compile from goal via IntentCompiler
                try:
                    from self_improve import IntentCompiler
                    intent = IntentCompiler.compile(task.goal)
                    if intent and intent["tool"] == "codeforge":
                        return intent["args"]
                except:
                    pass
        elif task.tool == "steganography" and task.args.get("action") == "decode":
            # try last_stego from memory kv
            if self.memory:
                last = self.memory.get_kv("last_stego")
                if last and last != task.args.get("stego"):
                    return {"action": "decode", "stego": last}
        return None

    def should_continue(self, state: VortexState) -> bool:
        # continue if no failures or if failures are recoverable
        failed = state.failed_tasks()
        return len(failed) == 0 or any(t.retries < t.max_retries for t in failed)
