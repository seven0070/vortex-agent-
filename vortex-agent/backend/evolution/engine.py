"""
Vortex Evolution Engine v1 — real, not simulated.

Weakness → Hypothesis → Isolated git worktree → Actual code patch →
Real tests → Real benchmark → Compare LKG → Council + Resolution →
Security → Governance → Canary → Monitor → Promote or rollback
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .canary import CanaryRunner
from .compiler import set_overlay
from .overlay import (
    Overlay,
    activate,
    get_active,
    load_current,
    load_last_known_good,
    load_pointers,
    next_generation_id,
    release_path,
    releases_dir,
    save_pointers,
)
from .patcher import CandidatePatcher
from .promotion import PromotionPolicy, overlay_regressions
from .rollback import RollbackManager
from .sandbox import SandboxRunner
from .security import SecurityScanner
from .harness import run_suite


class WeaknessFinder:
    def __init__(self, memory):
        self.memory = memory

    def find(self, traces: List[Dict] = None, eval_result: Dict = None) -> List[Dict[str, Any]]:
        weaknesses = []
        traces = traces or (self.memory.get_traces(50) if self.memory else [])
        low = [t for t in traces if (t.get("score") or 0) < 0.5]
        if low:
            tools = Counter(t.get("tool") for t in low if t.get("tool"))
            for tool, cnt in tools.most_common(3):
                if cnt >= 2:
                    weaknesses.append({
                        "type": "tool_failure",
                        "target": tool,
                        "count": cnt,
                        "severity": min(1.0, cnt / 5),
                        "evidence": [f"{t['task'][:60]} → {t.get('status')}" for t in low if t.get("tool") == tool][:3],
                    })
        if eval_result:
            for case in eval_result.get("cases", []):
                if not case.get("ok"):
                    weaknesses.append({
                        "type": "eval_failure",
                        "target": case.get("name"),
                        "severity": 0.8 if "chain" in str(case.get("name")) else 0.7,
                        "evidence": [str(case.get("reply", ""))[:100]],
                    })
        try:
            lessons = self.memory.get_lessons(True) if self.memory else []
            for lesson in lessons:
                if lesson.get("losses", 0) > lesson.get("wins", 0):
                    weaknesses.append({
                        "type": "lesson_loss",
                        "target": lesson.get("trigger"),
                        "severity": 0.5,
                        "evidence": [f"{lesson['trigger']} → {lesson['action']} {lesson['losses']}l"],
                    })
        except Exception:
            pass

        overlay = get_active().data.get("compiler") or {}
        if not overlay.get("chained_arithmetic"):
            weaknesses.append({
                "type": "eval_failure",
                "target": "reasoning-chain",
                "severity": 0.85,
                "evidence": ["chained arithmetic not enabled on current overlay"],
            })
        if not overlay.get("power_operator"):
            weaknesses.append({
                "type": "eval_failure",
                "target": "power-operator",
                "severity": 0.7,
                "evidence": ["power operator not enabled on current overlay"],
            })
        if not weaknesses:
            weaknesses.append({
                "type": "general",
                "target": "routing",
                "severity": 0.3,
                "evidence": ["no major failures, seek incremental gain"],
            })
        return weaknesses[:6]


class HypothesisGenerator:
    def generate(self, weakness: Dict[str, Any]) -> List[Dict[str, Any]]:
        hyps = []
        wtype = weakness.get("type")
        target = weakness.get("target")
        if wtype == "tool_failure":
            hyps.append({
                "hypothesis": f"Improve routing to {target} with better arg compilation",
                "change_set": [{"file": "overlay.json", "type": "router_improve", "target": target}],
                "confidence": 0.7,
            })
            hyps.append({
                "hypothesis": f"Add retry mutation for {target}",
                "change_set": [{"file": "overlay.json", "type": "retry_improve", "target": target}],
                "confidence": 0.65,
            })
        if wtype == "eval_failure" or target in ("reasoning-chain", "power-operator"):
            hyps.append({
                "hypothesis": f"Fix {target} by enabling chained arithmetic and power in the overlay compiler",
                "change_set": [{"file": "evolution/compiler.py", "type": "compiler_improve", "target": target}],
                "confidence": 0.9,
            })
        if wtype == "lesson_loss":
            hyps.append({
                "hypothesis": f"Adjust confidence for lesson {target}",
                "change_set": [{"file": "overlay.json", "type": "lesson_tune", "target": target}],
                "confidence": 0.6,
            })
        if not hyps:
            hyps.append({
                "hypothesis": "Enable missing compiler capabilities and boost recent router weights",
                "change_set": [{"file": "overlay.json", "type": "compiler_improve", "target": "reasoning-chain"}],
                "confidence": 0.75,
            })
        return hyps


class BenchmarkRunner:
    """Overlay-level regression benchmark. Does not mock scores."""

    def __init__(self, agent=None):
        self.agent = agent

    def run_overlay(self, overlay: Dict[str, Any], fixtures: Dict[str, Any]) -> Dict[str, Any]:
        return run_suite(overlay, fixtures, include_capability=True)

    def run(self, candidate: Dict[str, Any] = None, baseline: bool = False,
            comprehensive: bool = False) -> Dict[str, Any]:
        fixtures = {}
        if candidate and candidate.get("checkout_dir"):
            fix_path = Path(candidate["checkout_dir"]) / "fixtures.json"
            if fix_path.exists():
                fixtures = json.loads(fix_path.read_text())
        if not fixtures:
            from pathlib import Path as P
            stock = P(__file__).resolve().parent.parent / "tests" / "fixtures" / "golden_tasks.json"
            if stock.exists():
                fixtures = json.loads(stock.read_text())
        overlay = (candidate or {}).get("overlay") if candidate and not baseline else get_active().data
        if baseline:
            overlay = load_last_known_good().data
        result = self.run_overlay(overlay or {}, fixtures)
        result["timestamp"] = datetime.now().isoformat()
        result["baseline"] = baseline
        if comprehensive and self.agent:
            try:
                from evals import run_suite as agent_suite
                suite = agent_suite(self.agent, persist=False, name="benchmark_agent")
                result["agent_suite"] = {
                    "score": suite.get("score"),
                    "passed": suite.get("passed"),
                    "total": suite.get("total"),
                }
            except Exception as e:
                result["agent_suite_error"] = str(e)[:200]
        if candidate is not None and not baseline:
            candidate["benchmark_results"] = result
        return result


class EvolutionEngine:
    def __init__(self, agent, memory=None, governance=None, observability=None):
        self.agent = agent
        self.memory = memory or getattr(agent, "memory", None)
        self.governance = governance
        self.observability = observability
        self.releases_base = releases_dir()
        self.weakness_finder = WeaknessFinder(self.memory)
        self.hypothesis_gen = HypothesisGenerator()
        self.candidate_gen = CandidatePatcher(memory=self.memory, base_path=self.releases_base)
        self.sandbox = SandboxRunner()
        self.benchmark = BenchmarkRunner(agent=self.agent)
        self.security = SecurityScanner()
        self.policy = PromotionPolicy()
        self.canary = CanaryRunner(agent=self.agent)
        self.rollback = RollbackManager(agent=self.agent, memory=self.memory)
        self.history: List[Dict[str, Any]] = []
        # ensure live compiler matches persisted CURRENT overlay
        activate(load_current())

    def observe(self) -> Dict[str, Any]:
        traces = self.memory.get_traces(40) if self.memory else []
        return {
            "traces": len(traces),
            "avg_score": sum(t.get("score", 0) for t in traces) / len(traces) if traces else 0,
            "overlay_generation": get_active().generation_id,
            "pointers": load_pointers(),
        }

    def find_weaknesses(self, eval_result: Dict = None) -> List[Dict]:
        return self.weakness_finder.find(eval_result=eval_result)

    def _fixtures_for(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        path = Path(candidate.get("checkout_dir") or "") / "fixtures.json"
        if path.exists():
            return json.loads(path.read_text())
        stock = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "golden_tasks.json"
        if stock.exists():
            return json.loads(stock.read_text())
        return {"regression": [], "capability": [], "canary": []}

    def _authorize(self, operation: str, candidate: Dict[str, Any], gates: Dict = None) -> Dict[str, Any]:
        if not self.governance:
            return {"action": "ALLOW", "reason": "no governance loaded"}
        authorize = getattr(self.governance, "authorize_evolution", None)
        if authorize:
            return authorize(operation=operation, candidate=candidate, gates=gates, agent="improver")
        dec = self.governance.evaluate(
            task=f"self-improvement {operation}",
            context={
                "candidate": candidate.get("generation_id"),
                "isolated_candidate": True,
                "production_write": bool(candidate.get("production_write")),
                "evolution_gates_passed": bool((gates or {}).get("all_passed")),
                "gates": gates or {},
            },
            agent="improver",
            action=operation,
        )
        return dec

    def evolve_once(self, eval_result: Dict = None) -> Dict[str, Any]:
        if self.agent and getattr(self.agent, "sovereign", None):
            try:
                self.agent.sovereign.state.set_mode("evolving")
            except Exception:
                pass

        parent_overlay = load_current()
        fixtures_stock = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "golden_tasks.json"
        fixtures = json.loads(fixtures_stock.read_text()) if fixtures_stock.exists() else {}
        baseline = self.benchmark.run_overlay(parent_overlay.data, fixtures)

        weaknesses = self.find_weaknesses(eval_result)
        weakness = max(weaknesses, key=lambda w: w.get("severity", 0))
        hypotheses = self.hypothesis_gen.generate(weakness)
        hypothesis = max(hypotheses, key=lambda h: h.get("confidence", 0))

        parent_gen = parent_overlay.generation_id
        if self.memory:
            try:
                parent_gen = max(parent_gen, int(self.memory.current_generation() or 0))
            except Exception:
                pass

        auth = self._authorize("patch", {"generation_id": parent_gen + 1, "production_write": False})
        if auth.get("action") == "DENY":
            return {"decision": "reject", "reason": f"governance deny patch: {auth.get('reason')}", "baseline": baseline}

        candidate = self.candidate_gen.create_candidate(
            parent_gen, hypothesis, hypothesis.get("change_set", []), parent_overlay=parent_overlay
        )
        candidate["weakness"] = weakness

        sandbox_res = self.sandbox.run_tests(candidate)
        if not sandbox_res.get("passed"):
            candidate["decision"] = "reject"
            candidate["reason"] = "sandbox failed"
            candidate["status"] = "sandbox_failed"
            self._cleanup_workspace(candidate)
            self._save_candidate(candidate)
            self._restore_operational()
            return candidate

        new_bench = self.benchmark.run(candidate=candidate, baseline=False)
        base_cases = baseline.get("cases") or []
        regressions, critical = overlay_regressions(base_cases, new_bench.get("cases") or [])
        # capability tests that baseline failed are not regressions
        new_bench["regressions"] = regressions
        new_bench["critical_regressions"] = critical
        candidate["benchmark_results"] = new_bench

        sec_res = self.security.scan(candidate)
        if not sec_res.get("passed"):
            candidate["decision"] = "reject"
            candidate["reason"] = f"security failed risk={sec_res.get('risk_score')}"
            self._cleanup_workspace(candidate)
            self._save_candidate(candidate)
            self._restore_operational()
            return candidate

        # Council generates views; Resolution selects; Governance authorizes later.
        review = self._council_and_resolve(candidate, baseline, new_bench)
        candidate["council"] = review.get("council")
        candidate["resolution"] = review.get("resolution")
        if not review.get("proceed"):
            candidate["decision"] = "rejected"
            candidate["reason"] = review.get("reason") or "council/resolution rejected candidate"
            candidate["status"] = "rejected"
            self._cleanup_workspace(candidate)
            self._save_candidate(candidate)
            self._restore_operational()
            return candidate

        canary_res = self.canary.run(candidate, parent_overlay, fixtures=self._fixtures_for(candidate))
        if not canary_res.get("passed"):
            rb = self.rollback.rollback(
                reason="canary failed: " + ",".join(canary_res.get("failed_cases") or []),
                failed_generation=candidate["generation_id"],
            )
            candidate["decision"] = "canary_failed"
            candidate["status"] = "rolled_back"
            candidate["reason"] = rb["reason"]
            candidate["rollback"] = rb
            self._cleanup_workspace(candidate)
            self._save_candidate(candidate)
            self._restore_operational()
            return candidate

        policy = self.policy.decide(
            baseline=baseline,
            candidate=new_bench,
            security=sec_res,
            tests=sandbox_res.get("result") or sandbox_res,
            canary=canary_res,
        )
        candidate["promotion_policy"] = policy

        auth = self._authorize("promote", candidate, gates=policy)
        if auth.get("action") == "DENY":
            self.rollback.rollback("governance deny promote", candidate["generation_id"])
            candidate["decision"] = "reject"
            candidate["reason"] = f"governance deny: {auth.get('reason')}"
            candidate["status"] = "rejected"
            self._save_candidate(candidate)
            self._restore_operational()
            return candidate

        if not policy.get("all_passed"):
            candidate["decision"] = "rejected"
            candidate["reason"] = policy.get("reason")
            candidate["status"] = "rejected"
            self._save_candidate(candidate)
            self._restore_operational()
            return candidate

        deployed = self._promote(candidate, new_bench, hypothesis)
        candidate.update(deployed)
        candidate["monitor"] = {"phase": "monitoring", "started_at": datetime.now().isoformat()}
        self._save_candidate(candidate)
        self.history.append(candidate)
        if self.memory:
            try:
                self.memory.remember(
                    f"evolution promoted v{candidate['generation_id']:03d}: {candidate.get('reason')}",
                    kind="event",
                    meta={"generation": candidate["generation_id"], "score": new_bench.get("score")},
                )
            except Exception:
                pass
        return candidate

    def _council_and_resolve(self, candidate: Dict[str, Any], baseline: Dict, bench: Dict) -> Dict[str, Any]:
        """Council = competing views. Resolution = which view wins. Does not execute."""
        bq = float(baseline.get("quality", baseline.get("score", 0)) or 0)
        cq = float(bench.get("quality", bench.get("score", 0)) or 0)
        quality_up = cq > bq + 1e-9
        goal = (
            f"Promote evolution candidate v{int(candidate.get('generation_id') or 0):03d}? "
            f"hypothesis={((candidate.get('hypothesis') or {}).get('hypothesis') or '')[:120]}"
        )
        views = [
            {
                "id": "promote",
                "result": f"promote: quality {bq:.3f} → {cq:.3f}; patches={candidate.get('applied_patches')}",
                "confidence": 0.88 if quality_up else 0.35,
                "evidence": list(candidate.get("applied_patches") or [])[:6],
                "latency_ms": int((candidate.get("sandbox_result") or {}).get("latency_ms") or 0),
            },
            {
                "id": "reject",
                "result": "reject: keep last-known-good generation",
                "confidence": 0.28 if quality_up else 0.7,
                "evidence": list((bench.get("regressions") or []))[:6],
                "latency_ms": 0,
            },
        ]
        council_out = None
        agent = self.agent
        if agent and getattr(agent, "council", None):
            try:
                council_out = agent.council.deliberate(goal=goal, candidates=views)
                council_out = {
                    "executes": False,
                    "decision": council_out.get("decision"),
                    "confidence": council_out.get("confidence"),
                    "final": (council_out.get("final") or "")[:400],
                }
            except Exception as e:
                council_out = {"error": str(e)[:200], "executes": False}
        resolution = None
        if agent and getattr(agent, "resolver", None):
            try:
                resolution = agent.resolver.resolve(views, goal=goal)
            except Exception as e:
                resolution = {"action": "select", "error": str(e)[:200], "selected": {"id": "promote" if quality_up else "reject"}}
        selected_id = None
        if resolution:
            selected_id = (resolution.get("selected") or {}).get("id") or resolution.get("action")
        if selected_id == "reject" or (resolution or {}).get("action") in ("replan", "denied"):
            return {
                "proceed": False,
                "reason": f"resolution selected {selected_id or resolution.get('action')}",
                "council": council_out,
                "resolution": resolution,
            }
        return {"proceed": True, "council": council_out, "resolution": resolution}

    def _cleanup_workspace(self, candidate: Dict[str, Any]) -> None:
        wt = candidate.get("worktree_dir")
        if not wt:
            return
        try:
            self.candidate_gen.workspace.remove(
                wt, candidate.get("repo_root"), branch=candidate.get("git_branch")
            )
        except Exception:
            pass

    def _promote(self, candidate: Dict[str, Any], bench: Dict[str, Any], hypothesis: Dict) -> Dict[str, Any]:
        overlay = Overlay(candidate.get("overlay") or {}, source="promoted")
        activate(overlay)
        set_overlay(overlay.data)
        name = f"v{int(candidate['generation_id']):03d}"
        ptr = load_pointers()
        # last known good stays until this write — previous release dir is untouched
        ptr["last_known_good"] = name
        ptr["current"] = name
        ptr["canary"] = None
        save_pointers(ptr)

        gen_id = None
        if self.memory:
            try:
                gen_id = self.memory.save_generation(
                    candidate.get("parent_generation"),
                    bench.get("score", 0),
                    candidate.get("applied_patches") or candidate.get("change_set"),
                    f"evolution {bench.get('score')} — {hypothesis.get('hypothesis')}",
                )
            except Exception:
                pass
        if self.agent and getattr(self.agent, "sovereign", None):
            try:
                self.agent.sovereign.lifecycle.mark_deploy(candidate["generation_id"])
                self.agent.sovereign.state.set_mode("operational")
                self.agent.sovereign.state.update_generation(candidate["generation_id"])
                self.agent.sovereign.state.add_learning(
                    f"promoted {name}: {hypothesis.get('hypothesis')}"
                )
            except Exception:
                pass
        if self.observability:
            try:
                self.observability.metrics.inc("evolution_promoted")
            except Exception:
                pass
        return {
            "decision": "promoted",
            "reason": f"{name} earned promotion score={bench.get('score')}",
            "status": "deployed",
            "deployed_generation": gen_id,
        }

    def _restore_operational(self):
        activate(load_current())
        if self.agent and getattr(self.agent, "sovereign", None):
            try:
                self.agent.sovereign.state.set_mode("operational")
            except Exception:
                pass

    def _save_candidate(self, candidate: Dict[str, Any]):
        try:
            gen = candidate.get("generation_id", 0)
            release_dir = self.releases_base / f"v{int(gen):03d}"
            release_dir.mkdir(parents=True, exist_ok=True)
            payload = json.loads(json.dumps(candidate, default=str))
            (release_dir / "candidate_final.json").write_text(json.dumps(payload, indent=2))
            detail = {
                "generation_id": candidate.get("generation_id"),
                "parent_generation": candidate.get("parent_generation"),
                "change_set": candidate.get("change_set"),
                "applied_patches": candidate.get("applied_patches"),
                "benchmark_results": candidate.get("benchmark_results"),
                "security_results": candidate.get("security_results"),
                "performance_results": candidate.get("performance_results"),
                "canary_results": candidate.get("canary_results"),
                "promotion_policy": candidate.get("promotion_policy"),
                "decision": candidate.get("decision"),
                "reason": candidate.get("reason"),
                "hypothesis": candidate.get("hypothesis"),
                "workspace_mode": candidate.get("workspace_mode"),
                "git_branch": candidate.get("git_branch"),
                "council": candidate.get("council"),
                "resolution": candidate.get("resolution"),
            }
            (release_dir / "evolution_record.json").write_text(json.dumps(detail, default=str, indent=2))
            golden = release_dir / "golden"
            golden.mkdir(exist_ok=True)
            bench = candidate.get("benchmark_results") or {}
            (golden / "benchmark.json").write_text(json.dumps(bench, default=str, indent=2))
        except Exception as e:
            candidate["save_error"] = str(e)

    def status(self) -> Dict[str, Any]:
        return {
            "releases": len(list(self.releases_base.glob("v*"))),
            "pointers": load_pointers(),
            "active_overlay": get_active().data,
            "history": self.history[-5:],
            "last_candidate": self.history[-1] if self.history else None,
        }
