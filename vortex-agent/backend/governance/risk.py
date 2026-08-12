"""
Risk Engine — assesses risk of actions (0.0 safe → 1.0 dangerous)
"""
from __future__ import annotations
from typing import Dict, Any

class RiskEngine:
    def __init__(self):
        self.risk_keywords = {
            "rm -rf": 0.9,
            "drop table": 0.9,
            "delete": 0.6,
            "overwrite": 0.7,
            "deploy": 0.6,
            "self-improvement": 0.55,
            "modify orchestrator": 0.75,
            "execute": 0.4,
            "code": 0.35,
            "shell": 0.5,
            "filesystem": 0.5,
            "eval(": 0.7,
            "exec(": 0.8,
            "import os": 0.5,
            "subprocess": 0.6,
        }

    def assess(self, task: str = "", context: dict = None) -> float:
        context = context or {}
        score = 0.15  # base low

        low = task.lower()

        for kw, risk in self.risk_keywords.items():
            if kw in low:
                score = max(score, risk)

        # context adjustments
        if context.get("candidate_id"):
            # candidate from unknown source higher risk
            score += 0.05

        # tool-based risk
        tool = context.get("tool", "") or context.get("resource", "")
        if tool:
            tl = str(tool).lower()
            if "codeforge" in tl or "shell" in tl:
                score = max(score, 0.45)
            if "filesystem" in tl and "write" in low:
                score = max(score, 0.55)

        # agent-based
        agent = context.get("agent", "")
        if agent in ("improver", "architect") and "deploy" in low:
            score = max(score, 0.6)

        # legacy: result preview
        result = str(context.get("result", ""))[:500].lower()
        if "error" in result and "traceback" in result:
            score = max(score, 0.5)

        return min(1.0, round(score, 3))

    def is_acceptable(self, risk_score: float, threshold: float = 0.75) -> bool:
        return risk_score < threshold
