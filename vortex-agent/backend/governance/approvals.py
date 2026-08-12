"""
Approvals — tracks what requires human approval.
"""
from __future__ import annotations
from typing import Dict, Any
from datetime import datetime

class ApprovalManager:
    def __init__(self):
        self.pending: Dict[str, Dict[str, Any]] = {}
        self.approved: Dict[str, bool] = {}

    def requires_approval(self, task: str = "", risk_score: float = 0.0, agent: str = "chief") -> bool:
        low = task.lower()
        # high risk always requires approval
        if risk_score > 0.6:
            return True
        # production overwrites always require approval
        if any(k in low for k in ("overwrite production", "direct_deploy", "modify orchestrator")):
            return True
        # gated isolated overlay promote does not need a human if caller already passed gates
        if "self-improvement" in low or "evolution" in low or "promote" in low or "release" in low:
            return risk_score > 0.55
        # file writes to protected
        if "protected_file" in low or "orchestrator.py" in low:
            return True
        # improver deploying
        if agent == "improver" and ("cycle" in low or "promote" in low):
            return risk_score > 0.4
        return False

    def request(self, task: str, agent: str, context: dict = None) -> str:
        import uuid
        aid = f"appr_{uuid.uuid4().hex[:6]}"
        self.pending[aid] = {
            "task": task,
            "agent": agent,
            "context": context or {},
            "requested_at": datetime.now().isoformat(),
            "status": "pending"
        }
        return aid

    def approve(self, approval_id: str) -> bool:
        if approval_id in self.pending:
            self.pending[approval_id]["status"] = "approved"
            self.approved[approval_id] = True
            return True
        return False

    def deny(self, approval_id: str) -> bool:
        if approval_id in self.pending:
            self.pending[approval_id]["status"] = "denied"
            self.approved[approval_id] = False
            return True
        return False

    def is_approved(self, approval_id: str) -> bool:
        return self.approved.get(approval_id, False)
