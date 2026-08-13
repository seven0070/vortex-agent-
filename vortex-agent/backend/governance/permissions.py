"""
Permissions — who can do what on which resource.
"""
from __future__ import annotations
from typing import Dict, List

class PermissionManager:
    def __init__(self):
        # agent -> allowed actions/resources — more permissive for tool execution, stricter for core writes
        self.rules: Dict[str, Dict[str, List[str]]] = {
            "chief": {"allow": ["*"], "deny": []},
            "researcher": {"allow": ["read", "search", "recall", "research", "execute", "translate", "encode", "decode"], "deny": ["write_core", "deploy"]},
            "architect": {"allow": ["read", "write", "code", "execute", "benchmark", "search"], "deny": ["deploy_production"]},
            "cipher": {"allow": ["read", "translate", "encode", "decode", "security_check", "execute", "write", "search"], "deny": ["write_core"]},
            # modify_code lets the improver PROPOSE a verified diff. It never applies
            # one: code_mutation.ApprovalQueue still requires explicit human approval,
            # and direct_deploy stays denied.
            "improver": {"allow": ["read", "eval", "mutate", "test", "execute", "search", "modify_code"], "deny": ["direct_deploy"]},
            # legacy planning bots
            "planner": {"allow": ["read", "plan", "search", "execute"], "deny": ["deploy"]},
            "critic": {"allow": ["read", "evaluate", "search", "execute"], "deny": ["deploy"]},
            "strategist": {"allow": ["read", "plan", "evaluate", "search", "execute"], "deny": ["direct_write"]},
            "verifier": {"allow": ["read", "test", "verify", "search", "execute"], "deny": ["deploy"]},
            # council roles
            "Researcher": {"allow": ["read", "search", "execute"], "deny": ["deploy"]},
            "Engineer": {"allow": ["read", "write", "code", "execute", "search", "benchmark"], "deny": ["deploy_production"]},
            "Security": {"allow": ["read", "security_check", "audit", "execute", "translate", "encode", "decode", "search"], "deny": []},
            "Planner": {"allow": ["read", "plan", "search", "execute"], "deny": ["deploy"]},
            "Critic": {"allow": ["read", "evaluate", "search", "execute"], "deny": ["deploy"]},
            "Strategist": {"allow": ["read", "plan", "evaluate", "search", "execute"], "deny": ["direct_write"]},
            "Verifier": {"allow": ["read", "test", "verify", "search", "execute"], "deny": ["deploy"]},
        }
        self.protected_resources = [
            "orchestrator.py", "orchestration", "sovereign", "governance/policy.py",
            "self_improve.py", "memory.py", "evals.py"
        ]

    def check(self, agent: str = "chief", action: str = "execute", resource: str = "") -> bool:
        agent = agent or "chief"
        rule = self.rules.get(agent)
        if not rule:
            # unknown agent -> default deny risky
            if any(p in resource for p in self.protected_resources):
                return False
            return True

        # deny list first
        for deny in rule.get("deny", []):
            if deny == "*" or deny in action or deny in resource:
                # special: write_core
                if deny == "write_core" and ("write" in action or "modify" in action):
                    if any(p in resource for p in self.protected_resources):
                        return False
                elif deny in action or deny in resource or deny == "*":
                    return False

        allows = rule.get("allow", [])
        if "*" in allows:
            # still check protected
            if any(p in resource for p in self.protected_resources) and agent not in ("chief", "Engineer", "Governance"):
                # allow chief always, engineer with caution
                if agent in ("researcher", "Researcher", "Critic"):
                    return False
            return True

        for allow in allows:
            if allow in action or allow in resource or allow == "*":
                return True
            if allow == "read" and action in ("read", "search", "recall"):
                return True
            if allow == "write" and "write" in action:
                return True

        # fallback: if action is read-ish, allow more broadly
        if action in ("read", "search", "recall", "research"):
            return True

        return False

    def add_rule(self, agent: str, allow: List[str] = None, deny: List[str] = None):
        self.rules[agent] = {"allow": allow or [], "deny": deny or []}

    def is_protected(self, resource: str) -> bool:
        return any(p in resource for p in self.protected_resources)
