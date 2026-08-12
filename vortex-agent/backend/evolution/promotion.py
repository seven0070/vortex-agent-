"""
Multi-dimensional promotion policy.

A candidate must beat the last known-good generation on the dimensions that
matter. `new_score >= baseline - 0.001` is never sufficient by itself.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

LATENCY_LIMIT = 1.25
COST_LIMIT = 1.25
RELIABILITY_SLACK = 0.0


class PromotionPolicy:
    name = "vortex_v1_multidim"

    def decide(self, baseline: Dict[str, Any], candidate: Dict[str, Any],
               security: Dict[str, Any] = None, tests: Dict[str, Any] = None,
               canary: Dict[str, Any] = None) -> Dict[str, Any]:
        security = security or {}
        tests = tests or {}
        canary = canary or {}

        b_quality = float(baseline.get("quality", baseline.get("score", 0.0)) or 0.0)
        c_quality = float(candidate.get("quality", candidate.get("score", 0.0)) or 0.0)
        b_rel = float(baseline.get("reliability", 0.0) or 0.0)
        c_rel = float(candidate.get("reliability", 0.0) or 0.0)
        b_lat = float(baseline.get("latency_ms", 0.0) or 0.0)
        c_lat = float(candidate.get("latency_ms", 0.0) or 0.0)
        b_cost = float(baseline.get("cost", 1.0) or 1.0)
        c_cost = float(candidate.get("cost", 1.0) or 1.0)
        regressions = list(candidate.get("regressions") or [])
        critical = list(candidate.get("critical_regressions") or [])

        quality_up = c_quality > b_quality + 1e-9
        quality_ok = c_quality >= b_quality
        reliability_ok = c_rel >= b_rel - RELIABILITY_SLACK
        reliability_up = c_rel > b_rel + 1e-9
        latency_ok = True if b_lat <= 0 else c_lat <= b_lat * LATENCY_LIMIT
        latency_down = b_lat > 0 and c_lat < b_lat
        cost_ok = True if b_cost <= 0 else c_cost <= b_cost * COST_LIMIT
        cost_down = b_cost > 0 and c_cost < b_cost
        regressions_zero = len(critical) == 0 and len([r for r in regressions if r]) == 0
        # capability misses listed as regressions only if they were already passing
        tests_pass = bool(tests.get("passed", tests.get("tests_pass", False)))
        security_pass = bool(security.get("passed")) and float(security.get("risk_score", 1.0)) < 0.65
        canary_pass = True if not canary else bool(canary.get("passed"))

        gates = {
            "tests_pass": tests_pass,
            "security_pass": security_pass,
            "quality_ok": quality_ok,
            "reliability_ok": reliability_ok,
            "latency_ok": latency_ok,
            "cost_ok": cost_ok,
            "regressions_zero": regressions_zero,
            "no_critical_regression": len(critical) == 0,
            "canary_pass": canary_pass,
            "improvement_earned": quality_up or (quality_ok and (reliability_up or latency_down or cost_down)),
        }
        # hard requirement: quality must not drop, tests/security/canary/regressions must pass,
        # and at least one dimension must improve.
        hard = (
            gates["tests_pass"]
            and gates["security_pass"]
            and gates["quality_ok"]
            and gates["reliability_ok"]
            and gates["latency_ok"]
            and gates["cost_ok"]
            and gates["regressions_zero"]
            and gates["no_critical_regression"]
            and gates["canary_pass"]
            and gates["improvement_earned"]
        )
        reason_bits = [k for k, v in gates.items() if not v]
        decision = "promote" if hard else "reject"
        return {
            "decision": decision,
            "all_passed": hard,
            "gates": gates,
            "reason": "all gates passed" if hard else ("failed: " + ", ".join(reason_bits)),
            "dimensions": {
                "quality": {"baseline": b_quality, "candidate": c_quality, "dir": "up", "ok": quality_ok, "improved": quality_up},
                "reliability": {"baseline": b_rel, "candidate": c_rel, "dir": "up", "ok": reliability_ok, "improved": reliability_up},
                "security": {"baseline": 1.0 if security.get("passed") else 0.0, "candidate": 1.0 if security_pass else 0.0, "dir": "up", "ok": security_pass},
                "latency": {"baseline": b_lat, "candidate": c_lat, "dir": "down", "ok": latency_ok, "improved": latency_down},
                "cost": {"baseline": b_cost, "candidate": c_cost, "dir": "down", "ok": cost_ok, "improved": cost_down},
                "regressions": {"count": len(regressions), "critical": critical, "ok": regressions_zero},
            },
            "policy": self.name,
        }


def overlay_regressions(baseline_cases, candidate_cases) -> Tuple[list, list]:
    """Capability that baseline already passed must still pass."""
    base_ok = {c["name"]: c.get("ok") for c in (baseline_cases or [])}
    regressions, critical = [], []
    for c in candidate_cases or []:
        name = c.get("name")
        if base_ok.get(name) and not c.get("ok"):
            regressions.append(name)
            if c.get("critical") or c.get("category") == "regression":
                critical.append(name)
    return regressions, critical
