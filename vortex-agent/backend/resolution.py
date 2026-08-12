"""
Resolution layer — compares candidate solutions using correctness, reliability, evidence, cost, latency, risk, policy, historical success.

Candidates:
  Candidate A ─┐
  Candidate B ─┼──→ Resolver ─→ Best solution
  Candidate C ─┘

Resolver can say: "None of these solutions are good enough; return to planning."
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import math

@dataclass
class Candidate:
    id: str
    result: Any
    confidence: float = 0.5
    assigned_to: str = ""
    latency_ms: int = 0
    cost: float = 0.0  # estimated tokens / compute
    evidence: List[str] = None
    task_id: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []
        if self.metadata is None:
            self.metadata = {}

class VortexResolver:
    """
    Compares candidates on multi-dimensional criteria.

    Scoring dimensions (0-1):
    - correctness (does output match expected? heuristic)
    - reliability (confidence, past success)
    - evidence (how much supporting evidence)
    - cost (lower is better)
    - latency (lower is better)
    - risk (lower is better — security/policy)
    - policy_compliance (1 = fully compliant)
    - historical_success (based on memory)
    """
    def __init__(self, memory=None, governance=None, weights: Dict[str, float] = None):
        self.memory = memory
        self.governance = governance
        # tunable weights
        self.weights = weights or {
            "correctness": 0.25,
            "reliability": 0.15,
            "evidence": 0.15,
            "cost": 0.08,
            "latency": 0.07,
            "risk": 0.12,
            "policy_compliance": 0.10,
            "historical_success": 0.08,
        }

    def resolve(self, candidates: List[Dict[str, Any]], goal: str = "", state=None) -> Dict[str, Any]:
        if not candidates:
            return {
                "action": "replan",
                "reason": "no candidates to resolve",
                "final_response": "No viable candidates produced; returning to planning.",
                "selected": None,
                "scores": [],
            }

        # normalize to Candidate objects
        normed = self._normalize_candidates(candidates)

        # score each
        scored = []
        for cand in normed:
            scores = self._score_candidate(cand, goal, state)
            total = self._weighted_total(scores)
            scored.append({
                "candidate": cand,
                "scores": scores,
                "total": total,
            })

        scored.sort(key=lambda x: -x["total"])

        # check if best is good enough
        best = scored[0] if scored else None
        if not best or best["total"] < 0.35:
            return {
                "action": "replan",
                "reason": f"best candidate score too low: {best['total'] if best else 0:.2f}",
                "final_response": "",
                "selected": None,
                "scores": scored,
                "threshold": 0.35,
            }

        # if governance denies
        if self.governance and best:
            allowed = self._governance_check(best["candidate"], goal)
            if not allowed:
                # try next
                for alt in scored[1:]:
                    if self._governance_check(alt["candidate"], goal):
                        best = alt
                        break
                else:
                    return {
                        "action": "denied",
                        "reason": "governance denied all candidates",
                        "final_response": "All candidates denied by governance policy.",
                        "scores": scored,
                    }

        selected = best["candidate"]
        final_response = self._extract_final(selected.result)

        return {
            "action": "select",
            "selected": {
                "id": selected.id,
                "result": selected.result,
                "final_response": final_response,
                "confidence": selected.confidence,
                "assigned_to": selected.assigned_to,
                "task_id": selected.task_id,
                "scores": best["scores"],
                "total_score": best["total"],
            },
            "final_response": final_response,
            "runner_up": scored[1]["candidate"].id if len(scored) > 1 else None,
            "scores": [{"id": s["candidate"].id, "total": s["total"], "scores": s["scores"]} for s in scored],
            "goal": goal,
            "timestamp": datetime.now().isoformat(),
        }

    def _normalize_candidates(self, raw: List[Dict[str, Any]]) -> List[Candidate]:
        out = []
        for i, r in enumerate(raw):
            if isinstance(r, Candidate):
                out.append(r)
                continue
            # dict or raw string
            if isinstance(r, str):
                r = {"result": r}
            cid = r.get("id") or r.get("task_id") or f"cand_{i}"
            result = r.get("result") or r.get("text") or r.get("final") or str(r)
            conf = r.get("confidence") or r.get("score") or 0.6
            out.append(Candidate(
                id=str(cid),
                result=result,
                confidence=float(conf),
                assigned_to=r.get("assigned_to", ""),
                latency_ms=int(r.get("latency_ms", 0)),
                cost=float(r.get("cost", 0.0)),
                evidence=r.get("evidence") or [str(result)[:200]],
                task_id=r.get("task_id", ""),
                metadata=r
            ))
        return out

    def _score_candidate(self, cand: Candidate, goal: str, state=None) -> Dict[str, float]:
        # correctness heuristic
        correctness = self._estimate_correctness(cand, goal)

        # reliability from confidence and history
        reliability = self._estimate_reliability(cand)

        # evidence strength
        evidence_score = min(1.0, len(cand.evidence) * 0.3 + (0.2 if any(len(e) > 50 for e in cand.evidence) else 0))

        # cost: inverse of cost (assume 0-1000)
        cost_norm = max(0.1, 1.0 - (cand.cost / 1000.0))

        # latency: inverse (assume 0-5000ms)
        latency_norm = max(0.1, 1.0 - (cand.latency_ms / 5000.0))

        # risk: check for risky patterns
        risk_score = self._estimate_risk(cand)  # 0-1 where 1 = safe

        # policy compliance
        policy = self._estimate_policy_compliance(cand)

        # historical success from memory
        hist = self._estimate_historical(cand)

        return {
            "correctness": round(correctness, 3),
            "reliability": round(reliability, 3),
            "evidence": round(evidence_score, 3),
            "cost": round(cost_norm, 3),
            "latency": round(latency_norm, 3),
            "risk": round(risk_score, 3),
            "policy_compliance": round(policy, 3),
            "historical_success": round(hist, 3),
        }

    def _estimate_correctness(self, cand: Candidate, goal: str) -> float:
        # heuristic: if result contains error markers → low
        res = str(cand.result).lower()
        if "error" in res or "failed" in res or "exception" in res:
            return 0.2
        # if goal asks for number and result contains number → higher
        if any(k in goal.lower() for k in ("what is", "calculate", "sum", "fibonacci")):
            if any(ch.isdigit() for ch in res):
                return 0.85
        # confidence based
        if cand.confidence > 0.8:
            return 0.8
        if cand.confidence > 0.5:
            return 0.6
        return 0.5

    def _estimate_reliability(self, cand: Candidate) -> float:
        # based on confidence and assigned agent historical
        base = cand.confidence
        # if architect/engineer produced code result, consider more reliable if output long
        if cand.assigned_to in ("Engineer", "architect") and len(str(cand.result)) > 20:
            base += 0.1
        return min(0.95, max(0.1, base))

    def _estimate_risk(self, cand: Candidate) -> float:
        # risk safe score: 1 = safe, 0 = risky
        res = str(cand.result).lower()
        risky = ("rm -rf", "eval(", "exec(", "import os", "subprocess", "delete", "drop table")
        if any(r in res for r in risky):
            return 0.3
        if cand.assigned_to == "Security":
            return 0.9
        return 0.75

    def _estimate_policy_compliance(self, cand: Candidate) -> float:
        if self.governance:
            try:
                dec = self.governance.evaluate(task=str(cand.result)[:200], context={"candidate_id": cand.id})
                if dec.get("action") == "ALLOW":
                    return 1.0
                if dec.get("action") == "DENY":
                    return 0.1
                if dec.get("action") == "ESCALATE":
                    return 0.6
            except:
                pass
        return 0.85

    def _estimate_historical(self, cand: Candidate) -> float:
        # look at traces if memory available
        if self.memory:
            try:
                traces = self.memory.get_traces(50)
                # check if similar tasks with same bot succeeded
                bot = cand.assigned_to
                if bot:
                    bot_traces = [t for t in traces if t.get("bot") == bot or t.get("route") == bot]
                    if bot_traces:
                        avg = sum(t.get("score", 0.5) for t in bot_traces) / len(bot_traces)
                        return avg
            except:
                pass
        return 0.6

    def _weighted_total(self, scores: Dict[str, float]) -> float:
        total = 0.0
        for k, w in self.weights.items():
            total += scores.get(k, 0.5) * w
        return round(total, 4)

    def _governance_check(self, cand: Candidate, goal: str) -> bool:
        if not self.governance:
            return True
        try:
            dec = self.governance.evaluate(task=goal, context={"candidate": cand.id, "result": str(cand.result)[:300]})
            return dec.get("action") != "DENY"
        except:
            return True

    def _extract_final(self, result) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            # tool result
            if "output" in result.get("data", {}):
                return result["data"]["output"]
            if "translated" in result.get("data", {}):
                return str(result["data"]["translated"])
            if "encoded" in result.get("data", {}):
                return str(result["data"]["encoded"])
            if "decoded" in result.get("data", {}):
                return str(result["data"]["decoded"])
        return str(result)[:2000]
