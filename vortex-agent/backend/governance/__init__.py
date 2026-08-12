"""Governance — OPA-style explicit policy decisions outside LLM."""
from .policy import PolicyEngine, Policy, PolicyResult
from .permissions import PermissionManager
from .approvals import ApprovalManager
from .risk import RiskEngine
from .audit import AuditLog

class Governance:
    """
    Unified governance facade (layer 6).
    Evaluates:
      Is agent allowed?
      Is file protected?
      Does change require approval?
      Does test suite pass?
      Does security scan pass?
      Is risk acceptable?
    → ALLOW / DENY / ESCALATE
    """
    def __init__(self, memory=None):
        self.policy = PolicyEngine()
        self.permissions = PermissionManager()
        self.approvals = ApprovalManager()
        self.risk = RiskEngine()
        self.audit = AuditLog(memory=memory)
        self.memory = memory

    def evaluate(self, task: str = "", context: dict = None, agent: str = "chief", action: str = "execute") -> dict:
        context = context or {}
        # 1. policy
        policy_result = self.policy.evaluate(task=task, agent=agent, action=action, context=context)

        # 2. permissions
        perm_allowed = self.permissions.check(agent=agent, action=action, resource=context.get("resource", task))

        # 3. risk
        risk_score = self.risk.assess(task=task, context=context)

        # 4. approvals needed?
        needs_approval = self.approvals.requires_approval(task=task, risk_score=risk_score, agent=agent)

        # decision logic
        if not perm_allowed:
            decision = "DENY"
            reason = f"permission denied for {agent} → {action}"
        elif policy_result.action == "DENY":
            decision = "DENY"
            reason = policy_result.reason
        elif risk_score > 0.8:
            decision = "DENY"
            reason = f"risk too high: {risk_score:.2f}"
        elif needs_approval or policy_result.action == "ESCALATE" or risk_score > 0.55:
            decision = "ESCALATE"
            reason = f"escalation required: policy={policy_result.action} risk={risk_score:.2f} approval={needs_approval}"
        else:
            decision = "ALLOW"
            reason = "passed policy, permissions, risk"

        result = {
            "action": decision,
            "reason": reason,
            "policy": policy_result.to_dict() if hasattr(policy_result, 'to_dict') else str(policy_result),
            "risk_score": risk_score,
            "permissions": perm_allowed,
            "needs_approval": needs_approval,
        }

        # audit log
        self.audit.log(task=task, agent=agent, action=action, decision=decision, context=context, reason=reason)

        return result

    def allow(self, *args, **kwargs):
        return self.evaluate(*args, **kwargs).get("action") == "ALLOW"

__all__ = ["Governance", "PolicyEngine", "PermissionManager", "ApprovalManager", "RiskEngine", "AuditLog"]
