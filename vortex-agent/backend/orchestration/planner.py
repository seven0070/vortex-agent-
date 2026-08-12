"""
Planner — decomposes goal into tasks (Understand → Plan → Decompose)
Inspired by LangGraph's stateful planning and Microsoft Agent Framework sequential patterns.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional
from .state import VortexState, TaskNode, WorkflowPhase, TaskStatus

class Planner:
    def __init__(self, memory=None):
        self.memory = memory

    def understand(self, state: VortexState) -> VortexState:
        """Phase 1: understand goal, inject memory, form working context."""
        goal = state.goal or state.original_message
        state.transition(WorkflowPhase.UNDERSTAND, f"understanding: {goal[:80]}")

        # memory injection if available
        ctx = {}
        if self.memory and hasattr(self.memory, 'full_context_for_orchestrator'):
            try:
                ctx = self.memory.full_context_for_orchestrator(goal)
                state.memories_used = ctx.get("relevant_memories", [])[:8]
            except Exception as e:
                state.trace(WorkflowPhase.UNDERSTAND, f"memory recall failed: {e}")

        # identify intent patterns
        intent = self._classify_intent(goal)
        state.metadata["intent"] = intent
        state.metadata["memory_context"] = ctx
        state.trace(WorkflowPhase.UNDERSTAND, f"classified intent={intent}", {"intent": intent, "memories": len(state.memories_used)})
        return state

    def plan(self, state: VortexState) -> VortexState:
        """Phase 2: high-level plan strategy."""
        state.transition(WorkflowPhase.PLAN, "generating plan")
        intent = state.metadata.get("intent", "general")
        goal = state.goal

        # heuristic planning based on intent
        if intent == "multi_step":
            strategy = "decompose_then_council_then_resolve"
        elif intent in ("code", "research", "secure", "math"):
            strategy = "single_tool_with_verification"
        else:
            strategy = "swarm_collab"

        state.metadata["strategy"] = strategy
        state.trace(WorkflowPhase.PLAN, f"strategy={strategy}")
        return state

    def decompose(self, state: VortexState) -> VortexState:
        """Phase 3: break into executable task nodes."""
        state.transition(WorkflowPhase.DECOMPOSE, "decomposing")
        goal = state.goal
        intent = state.metadata.get("intent", "general")

        tasks = self._decompose_goal(goal, intent)

        for t in tasks:
            node = state.add_task(
                goal=t["goal"],
                description=t.get("description", ""),
                tool=t.get("tool"),
                args=t.get("args", {})
            )
            node.status = TaskStatus.PLANNED

        state.trace(WorkflowPhase.DECOMPOSE, f"decomposed into {len(tasks)} tasks")
        return state

    # ----- helpers -----
    def _classify_intent(self, text: str) -> str:
        low = text.lower()
        # multi-step indicators
        if any(k in low for k in ("research and build", "analyze and secure", "investigate", "comprehensive", "swarm")):
            return "multi_step"
        if any(k in low for k in ("fibonacci", "benchmark", "calculate", "code", "python", "script", "run")):
            return "code"
        if any(k in low for k in ("research", "find", "search", "investigate", "what is", "explain")):
            return "research"
        if any(k in low for k in ("hide", "encode", "steg", "secure", "encrypt", "translate", "conlang", "obfuscate")):
            return "secure"
        if any(k in low for k in ("sum", "multiply", "times", "plus", "math")):
            return "math"
        if any(k in low for k in ("evolve", "improve", "self-improve", "rsi")):
            return "self_improve"
        return "general"

    def _decompose_goal(self, goal: str, intent: str) -> List[Dict[str, Any]]:
        low = goal.lower()
        tasks = []

        def _compile_code_from_goal(g: str) -> Dict[str, Any]:
            # try IntentCompiler first (math, fib etc.)
            try:
                from self_improve import IntentCompiler
                ic = IntentCompiler.compile(g)
                if ic and ic.get("tool") == "codeforge":
                    return ic.get("args", {})
            except:
                pass
            # fallback: if contains times/multiply etc, try simple
            import re
            m = re.search(r"(\d+)\s*(?:times|x|\*)\s*(\d+)", g, re.I)
            if m:
                return {"code": f"print({m.group(1)} * {m.group(2)})"}
            return {"code": f"print({g[:80]})"}

        if intent == "multi_step":
            if any(k in low for k in ("research", "analyze", "investigate")):
                tasks.append({"goal": f"Research: {goal}", "description": "Gather context and memory", "tool": None})
            if any(k in low for k in ("code", "build", "script", "calculate", "fibonacci", "benchmark")):
                args = _compile_code_from_goal(goal)
                tasks.append({"goal": f"Build: {goal}", "description": "Implement solution", "tool": "codeforge", "args": args})
            if any(k in low for k in ("secure", "hide", "encrypt")):
                tasks.append({"goal": f"Secure: {goal}", "description": "Secure or obfuscate", "tool": "steganography"})
            if not tasks:
                tasks.append({"goal": goal, "description": "General decomposed task"})

        elif intent == "code":
            args = _compile_code_from_goal(goal)
            tasks.append({"goal": goal, "description": "Execute code task", "tool": "codeforge", "args": args})
            tasks.append({"goal": f"Verify: {goal}", "description": "Verify output", "tool": None})

        elif intent == "research":
            tasks.append({"goal": goal, "description": "Research with memory recall", "tool": None})

        elif intent == "secure":
            if "reveal" in low or "decode" in low:
                tasks.append({"goal": goal, "description": "Reveal payload", "tool": "steganography", "args": {"action": "decode"}})
            elif "translate" in low:
                tasks.append({"goal": goal, "description": "Translate to conlang", "tool": "glossopetrae", "args": {"text": goal}})
            else:
                tasks.append({"goal": goal, "description": "Hide payload", "tool": "steganography", "args": {"action": "encode"}})

        elif intent == "math":
            args = _compile_code_from_goal(goal)
            tasks.append({"goal": goal, "description": "Solve math via codeforge", "tool": "codeforge", "args": args})

        else:
            tasks.append({"goal": goal, "description": "General task"})

        # limit
        return tasks[:6]

    def replan_on_failure(self, state: VortexState, failed_tasks: List[TaskNode]) -> VortexState:
        """Called by recovery engine."""
        state.trace(WorkflowPhase.PLAN, f"replanning after {len(failed_tasks)} failures")
        for ft in failed_tasks:
            # create alternative task
            alt = state.add_task(
                goal=f"Alternative for: {ft.goal}",
                description=f"Retry with different approach (orig error: {ft.error})",
                parent_id=ft.id,
                tool=ft.tool,
                args=ft.args
            )
            alt.status = TaskStatus.PLANNED
        return state
