"""
Policy Engine — OPA-style explicit policy decisions.

Policies are declarative rules evaluated outside LLM logic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import re

@dataclass
class Policy:
    name: str
    description: str
    condition: str  # python expression or keyword
    action: str  # ALLOW, DENY, ESCALATE
    priority: int = 10
    enabled: bool = True

    def matches(self, task: str, agent: str, action: str, context: dict) -> bool:
        # simple pattern matching engine inspired by OPA Rego but Python-level
        cond = self.condition.lower()
        task_l = task.lower()
        # keywords
        if "protected_file" in cond:
            # check if context resource is protected
            res = str(context.get("resource", "")).lower()
            protected = ("orchestrator.py", "self_improve.py", "governance", "sovereign", "memory.py")
            if any(p in res for p in protected):
                return True
        if "deny:" in cond:
            needle = cond.split("deny:")[-1].strip()
            if needle and needle in task_l:
                return True
        if "escalate:" in cond:
            needle = cond.split("escalate:")[-1].strip()
            if needle and needle in task_l:
                return True
        if "agent:" in cond:
            needle = cond.split("agent:")[-1].strip()
            if agent.lower() == needle:
                return True
        if "action:" in cond:
            needle = cond.split("action:")[-1].strip()
            if action.lower() == needle:
                return True
        if "always" in cond:
            return True
        # regex fallback
        try:
            if re.search(cond, task_l):
                return True
        except:
            pass
        return False

@dataclass
class PolicyResult:
    action: str  # ALLOW, DENY, ESCALATE
    reason: str
    matched_policies: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "action": self.action,
            "reason": self.reason,
            "matched_policies": self.matched_policies,
            "context": self.context,
        }

class PolicyEngine:
    def __init__(self):
        self.policies: List[Policy] = []
        self._load_defaults()

    def _load_defaults(self):
        self.policies = [
            Policy(name="deny_dangerous_shell", description="Block rm -rf, etc", condition="deny:rm -rf", action="DENY", priority=100),
            Policy(name="deny_drop_table", description="Block DB destructive", condition="deny:drop table", action="DENY", priority=100),
            Policy(name="protect_core", description="Protect core files", condition="protected_file", action="ESCALATE", priority=90),
            Policy(name="escalate_code_mod", description="Code modification needs approval", condition="escalate:modify orchestrator", action="ESCALATE", priority=80),
            Policy(name="escalate_self_improve", description="Self-improve deploy escalates", condition="escalate:self-improvement", action="ESCALATE", priority=80),
            Policy(name="allow_research", description="Research is generally allowed", condition="research", action="ALLOW", priority=10),
            Policy(name="default_allow", description="Default allow", condition="always", action="ALLOW", priority=1),
        ]

    def add_policy(self, policy: Policy):
        self.policies.append(policy)
        self.policies.sort(key=lambda p: -p.priority)

    def evaluate(self, task: str = "", agent: str = "chief", action: str = "execute", context: dict = None) -> PolicyResult:
        context = context or {}
        matched = []
        # highest priority matching decides
        for pol in sorted(self.policies, key=lambda p: -p.priority):
            if not pol.enabled:
                continue
            if pol.matches(task, agent, action, context):
                matched.append(pol.name)
                # DENY overrides
                if pol.action == "DENY":
                    return PolicyResult(action="DENY", reason=f"policy {pol.name}: {pol.description}", matched_policies=matched, context=context)
                if pol.action == "ESCALATE":
                    return PolicyResult(action="ESCALATE", reason=f"policy {pol.name}: {pol.description}", matched_policies=matched, context=context)
                # ALLOW but continue to see if higher prio deny later? Actually sorted so first match wins unless allow and there is deny later? We sort high first so deny first.
                if pol.action == "ALLOW" and len(matched) == 1:
                    # keep looking for higher impact - but since sort high->low, we have highest first. So if first is allow, no higher deny. Return allow if no escalate.
                    pass

        # if no deny/escalate matched, allow
        if not matched:
            return PolicyResult(action="ALLOW", reason="no policy matched, default allow", matched_policies=[], context=context)

        # check if any escalate in matched
        for pol in self.policies:
            if pol.name in matched and pol.action == "ESCALATE":
                return PolicyResult(action="ESCALATE", reason=f"escalated by {pol.name}", matched_policies=matched, context=context)

        return PolicyResult(action="ALLOW", reason=f"allowed by {matched[0]}", matched_policies=matched, context=context)

    def list_policies(self) -> List[Dict[str, Any]]:
        return [{"name": p.name, "description": p.description, "action": p.action, "priority": p.priority, "enabled": p.enabled} for p in self.policies]
