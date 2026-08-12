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
        if context.get("evolution_gates_passed") and context.get("isolated_candidate") and not context.get("production_write"):
            needs_approval = False
        else:
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

    def authorize_evolution(self, operation: str, candidate: dict = None,
                            gates: dict = None, agent: str = "improver") -> dict:
        """
        Authoritative gate for self-modification.

        Isolated overlay patch/sandbox/canary/rollback is allowed.
        Promote is ALLOW only when every multi-dimensional gate passed
        and the candidate does not overwrite production source.
        Direct production writes are always DENY.
        """
        candidate = candidate or {}
        gates = gates or {}
        production_write = bool(candidate.get("production_write"))
        resource = str((candidate.get("change_set") or [{}])[0].get("file") or "overlay.json")

        if operation in ("overwrite_production", "direct_deploy") or production_write:
            result = {
                "action": "DENY",
                "reason": "production source overwrite is forbidden; use isolated overlay releases",
                "risk_score": 0.95,
                "permissions": False,
                "needs_approval": True,
            }
            self.audit.log(task=f"evolution:{operation}", agent=agent, action=operation,
                           decision="DENY", context=candidate, reason=result["reason"])
            return result

        if self.permissions.is_protected(resource) and operation == "promote" and production_write:
            result = {
                "action": "DENY",
                "reason": f"protected resource {resource}",
                "risk_score": 0.9,
                "permissions": False,
                "needs_approval": True,
            }
            self.audit.log(task=f"evolution:{operation}", agent=agent, action=operation,
                           decision="DENY", context={"resource": resource}, reason=result["reason"])
            return result

        if operation in ("patch", "sandbox", "canary", "rollback", "test"):
            result = {
                "action": "ALLOW",
                "reason": f"isolated evolution {operation} permitted",
                "risk_score": 0.25,
                "permissions": True,
                "needs_approval": False,
            }
            self.audit.log(task=f"evolution:{operation}", agent=agent, action=operation,
                           decision="ALLOW", context={"generation": candidate.get("generation_id")},
                           reason=result["reason"])
            return result

        if operation == "promote":
            if not gates.get("all_passed"):
                result = {
                    "action": "DENY",
                    "reason": f"promotion gates failed: {gates.get('reason', gates)}",
                    "risk_score": 0.7,
                    "permissions": True,
                    "needs_approval": True,
                    "gates": gates,
                }
                self.audit.log(task="evolution:promote", agent=agent, action="promote",
                               decision="DENY", context={"gates": gates}, reason=result["reason"])
                return result
            result = {
                "action": "ALLOW",
                "reason": "all evolution gates passed; overlay promote authorized",
                "risk_score": 0.3,
                "permissions": True,
                "needs_approval": False,
                "gates": gates,
            }
            self.audit.log(task="evolution:promote", agent=agent, action="promote",
                           decision="ALLOW", context={"generation": candidate.get("generation_id")},
                           reason=result["reason"])
            return result

        return self.evaluate(
            task=f"self-improvement {operation}",
            context={"candidate": candidate, "gates": gates, "isolated_candidate": True},
            agent=agent,
            action=operation,
        )

    def allow(self, *args, **kwargs):
        return self.evaluate(*args, **kwargs).get("action") == "ALLOW"

__all__ = ["Governance", "PolicyEngine", "PermissionManager", "ApprovalManager", "RiskEngine", "AuditLog"]
