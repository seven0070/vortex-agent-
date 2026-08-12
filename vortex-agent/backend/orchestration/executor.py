"""
Executor — runs tasks (LangGraph execute node + branching + durable execution)
"""
from __future__ import annotations
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from .state import VortexState, TaskNode, TaskStatus, WorkflowPhase

class Executor:
    def __init__(self, agent=None, tool_registry=None, memory=None, observability=None):
        self.agent = agent
        self.tools = tool_registry
        self.memory = memory
        self.obs = observability

    def execute(self, state: VortexState) -> VortexState:
        state.transition(WorkflowPhase.EXECUTE, f"executing {len(state.tasks)} tasks")
        for task in state.tasks:
            if task.status != TaskStatus.ROUTED:
                continue
            self._execute_single(task, state)

        # if all tasks produced result, move to observe
        success_count = sum(1 for t in state.tasks if t.status == TaskStatus.SUCCESS)
        state.trace(WorkflowPhase.EXECUTE, f"executed: {success_count}/{len(state.tasks)} succeeded")
        return state

    def _execute_single(self, task: TaskNode, state: VortexState):
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().isoformat()
        t0 = time.time()

        try:
            result = self._run_task_logic(task, state)
            latency = int((time.time() - t0)*1000)
            task.latency_ms = latency
            task.result = result
            task.status = TaskStatus.SUCCESS
            task.finished_at = datetime.now().isoformat()
            task.confidence = self._estimate_confidence(task, result)

            # log to memory / observability
            if self.memory:
                try:
                    self.memory.save_trace({
                        "generation": state.generation,
                        "task": task.goal,
                        "bot": task.assigned_to,
                        "route": task.assigned_to,
                        "tool": task.tool,
                        "status": "success",
                        "score": task.confidence,
                        "latency_ms": latency,
                        "detail": {"task_id": task.id, "result_preview": str(result)[:200]}
                    })
                except:
                    pass
            state.tool_calls.append({
                "task_id": task.id,
                "tool": task.tool,
                "assigned_to": task.assigned_to,
                "status": "success",
                "latency_ms": latency
            })
            state.trace(WorkflowPhase.EXECUTE, f"task {task.id} success ({latency}ms)", {"result": str(result)[:200]})

        except Exception as e:
            latency = int((time.time() - t0)*1000)
            task.error = str(e)[:500]
            task.latency_ms = latency
            task.retries += 1
            if task.retries < task.max_retries:
                task.status = TaskStatus.PENDING  # will be recovered
            else:
                task.status = TaskStatus.FAILED
            task.finished_at = datetime.now().isoformat()

            if self.memory:
                try:
                    self.memory.save_trace({
                        "generation": state.generation,
                        "task": task.goal,
                        "bot": task.assigned_to,
                        "route": task.assigned_to,
                        "tool": task.tool,
                        "status": "error",
                        "score": 0.1,
                        "latency_ms": latency,
                        "detail": {"error": task.error}
                    })
                except:
                    pass
            state.trace(WorkflowPhase.EXECUTE, f"task {task.id} failed: {e}", {"error": str(e)})

    def _run_task_logic(self, task: TaskNode, state: VortexState) -> Any:
        """Core execution: delegate to agent/bot or direct tool. Governance cannot be skipped."""
        gov = getattr(self.agent, "governance", None) if self.agent else None
        if gov and (task.tool or task.goal):
            dec = gov.evaluate(
                task=task.goal,
                context={"tool": task.tool, "args": task.args, "task_id": task.id},
                agent=task.assigned_to or "chief",
                action="execute",
            )
            if dec.get("action") == "DENY":
                raise RuntimeError(f"Governance DENY: {dec.get('reason')}")
        # if agent exists and has bots
        if self.agent and task.assigned_to and task.assigned_to.lower() != "chief":
            # try to find bot by role or name
            bot_name = None
            # map council role names to classic bot names
            role_to_bot = {
                "Researcher": "researcher",
                "Engineer": "architect",
                "Security": "cipher",
                "Planner": "chief",
                "Critic": "researcher",
                "Strategist": "chief",
                "Verifier": "architect",
            }
            bot_name = role_to_bot.get(task.assigned_to, task.assigned_to.lower())
            if bot_name in getattr(self.agent, 'bots', {}):
                # delegate to bot's handle
                # if task has tool, we try to have bot handle directly
                reply = self.agent.bots[bot_name].handle(task.goal)
                return reply
            elif hasattr(self.agent, 'bots') and "chief" in self.agent.bots:
                return self.agent.bots["chief"].handle(task.goal)

        # fallback: direct tool execution
        if task.tool and self.tools:
            # tools registry might be dict or ToolRegistry
            tool_obj = None
            if isinstance(self.tools, dict):
                tool_obj = self.tools.get(task.tool)
            else:
                # try get method
                try:
                    tool_obj = self.tools.get(task.tool)
                except:
                    pass
            if tool_obj:
                if hasattr(tool_obj, 'execute'):
                    return tool_obj.execute(**task.args)
                elif callable(tool_obj):
                    return tool_obj(**task.args)

        # if task.tool == codeforge and args missing code, try compile from goal
        if task.tool == "codeforge":
            if not task.args.get("code"):
                try:
                    from self_improve import IntentCompiler, compile_math
                    ic = IntentCompiler.compile(task.goal)
                    if ic and ic.get("args"):
                        task.args = ic.get("args")
                    elif compile_math(task.goal):
                        task.args = {"code": compile_math(task.goal)}
                    else:
                        # fallback simple print
                        task.args = {"code": f"print('{task.goal[:50]}')"}
                except Exception:
                    task.args = {"code": f"print('{task.goal[:50]}')"}

        # if tools is legacy TOOL_CLASSES dict
        legacy_tools = None
        try:
            from tools import TOOL_CLASSES
            legacy_tools = {t.name: t for t in TOOL_CLASSES}
        except:
            try:
                from tools_legacy import TOOL_CLASSES as LTC
                legacy_tools = {t.name: t for t in LTC}
            except:
                pass

        if task.tool and legacy_tools and task.tool in legacy_tools:
            tcls = legacy_tools[task.tool]
            return tcls.execute(**task.args)

        # last resort: if no tool, simulate result from goal memory
        return f"Task '{task.goal}' executed by {task.assigned_to or 'system'} (no tool)"

    def _estimate_confidence(self, task: TaskNode, result: Any) -> float:
        # heuristic confidence scoring
        if task.error:
            return 0.2
        res_str = str(result).lower()
        if "error" in res_str or "failed" in res_str:
            return 0.3
        if task.tool and "success" in res_str:
            return 0.85
        if task.result and len(str(task.result)) > 20:
            return 0.7
        return 0.6
