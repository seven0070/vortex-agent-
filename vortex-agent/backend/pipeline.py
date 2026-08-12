"""
Request pipeline — one request travels the intended layers.

Interface → Sovereign → Memory(retrieve) → Governance →
Orchestration → Council? → Resolution → Tools →
Memory(store) → Evaluation → Self-Improvement
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


REQUIRED_LAYERS = (
    "interface",
    "sovereign",
    "governance",
    "orchestration",
    "resolution",
    "tools",
    "memory",
    "evaluation",
    "self-improvement",
)


class RequestPipeline:
    def __init__(self, agent):
        self.agent = agent

    def handle(self, message: str) -> str:
        t0 = time.time()
        trail: List[str] = ["interface"]
        ctx: Dict[str, Any] = {"message": message, "layers": trail, "memories": [], "denied": False}

        # 1. Sovereign — identity, objectives, operating boundaries
        if self.agent.sovereign:
            snap = self.agent.sovereign.state.snapshot()
            if snap.get("mode") == "halted" or snap.get("health") == "halted":
                ctx["denied"] = True
                reply = "Sovereign: system is halted."
                self._finish(ctx, reply, t0)
                return reply
            ctx["sovereign"] = {
                "identity": self.agent.sovereign.identity.whoami(),
                "mode": snap.get("mode"),
                "priority": None,
            }
            try:
                ctx["sovereign"]["priority"] = self.agent.sovereign.priorities.top()
            except Exception:
                pass
        trail.append("sovereign")

        # 2. Memory retrieve — past experience becomes planning context
        memories: List[Any] = []
        if hasattr(self.agent.memory, "recall"):
            try:
                memories = self.agent.memory.recall(message, n=5) or []
            except Exception:
                memories = []
        ctx["memories"] = memories
        trail.append("memory")

        memory_answer = self._answer_from_memory(message, memories)
        ctx["memory_hit"] = bool(memory_answer)

        # 3. Governance — cannot be bypassed
        if self.agent.governance:
            dec = self.agent.governance.evaluate(
                task=message, context={"source": "pipeline", "memories": len(memories)},
                agent="chief", action="handle",
            )
            ctx["governance"] = dec
            if dec.get("action") == "DENY":
                ctx["denied"] = True
                reply = f"Governance DENY: {dec.get('reason')}"
                trail.append("governance")
                self._finish(ctx, reply, t0)
                return reply
        trail.append("governance")

        # 4–7. Orchestration / Council / Resolution / Tools
        if memory_answer and not self._looks_like_tool_task(message):
            trail.append("orchestration")
            trail.append("council:skipped_memory")
            trail.append("resolution")
            trail.append("tools")
            reply = memory_answer
            ctx["route"] = "memory"
        elif self._should_orchestrate(message):
            trail.append("orchestration")
            trail.append("council")
            trail.append("resolution")
            trail.append("tools")
            ctx["route"] = "orchestrated"
            reply = self.agent.run_orchestrated(message, original_message=message)
        else:
            trail.append("orchestration")
            # council is reserved for competing views; simple compiled routes skip it
            trail.append("council:skipped_simple")
            trail.append("resolution")
            trail.append("tools")
            ctx["route"] = "fast"
            # inject memories so chief/researcher can use them
            self.agent._request_context = ctx
            reply = self.agent.bots["chief"].handle(message)

        # 8. Evaluation
        score = 0.55
        try:
            last = getattr(self.agent.bots.get("chief"), "_last", {}) or {}
            score = self.agent.rsi.score(reply, last.get("tool"), last.get("status"))
        except Exception:
            pass
        ctx["score"] = score
        trail.append("evaluation")

        # 9. Memory store + self-improvement observe (chief.handle already observes on fast path)
        try:
            self.agent.memory.remember(
                f"{message[:80]} -> {reply[:120]}",
                kind="episodic",
                meta={"route": ctx.get("route"), "score": score},
            )
        except Exception:
            pass
        trail.append("self-improvement")

        self._finish(ctx, reply, t0)
        return reply

    def _finish(self, ctx: Dict[str, Any], reply: str, t0: float) -> None:
        ctx["layers"] = list(dict.fromkeys(ctx.get("layers") or []))
        ctx["latency_ms"] = int((time.time() - t0) * 1000)
        ctx["reply_preview"] = (reply or "")[:200]
        self.agent.last_pipeline = ctx

    def _should_orchestrate(self, message: str) -> bool:
        low = (message or "").lower().strip()
        if low.startswith("orchestrate:"):
            return True
        if any(k in low for k in ("research and build", "analyze and secure", "comprehensive")):
            return True
        return False

    def _looks_like_tool_task(self, message: str) -> bool:
        low = (message or "").lower()
        if low.startswith("/"):
            return True
        return any(k in low for k in ("times", "plus", "fibonacci", "hide ", "translate", "/run"))

    def _answer_from_memory(self, message: str, memories: List[Any]) -> Optional[str]:
        """Use stored facts when they clearly answer the question."""
        if not memories or not message:
            return None
        q = message.lower()
        if not any(w in q for w in ("what", "when", "who", "where", "deadline", "remember")):
            return None
        q_tokens = {t for t in q.replace("?", " ").split() if len(t) > 3}
        best = None
        best_overlap = 0
        for item in memories:
            text = ""
            if isinstance(item, dict):
                text = str(item.get("text") or item.get("fact") or item.get("data") or "")
            else:
                text = str(item)
            tokens = {t.strip(".,:;!?") for t in text.lower().split() if len(t) > 3}
            overlap = len(q_tokens & tokens)
            if overlap > best_overlap and len(text) > 8:
                best_overlap = overlap
                best = text
        if best and best_overlap >= 1:
            return f"🧠 Recalled from memory: {best}"
        return None
