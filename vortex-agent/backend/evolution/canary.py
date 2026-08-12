"""
Real canary: activate the candidate overlay, run live canary tasks, compare
against last-known-good on the same tasks. Failure restores the previous overlay.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .compiler import compile_any, set_overlay
from .harness import _safe_value, run_suite
from .overlay import Overlay, activate, get_active, load_pointers, release_path, save_pointers


class CanaryRunner:
    def __init__(self, agent=None):
        self.agent = agent

    def run(self, candidate: Dict[str, Any], baseline_overlay: Overlay,
            fixtures: Dict[str, Any] = None) -> Dict[str, Any]:
        fixtures = fixtures or {}
        canary_cases = fixtures.get("canary") or fixtures.get("regression") or []
        wrapped = {"regression": canary_cases, "capability": []}
        previous = get_active().copy()
        cand_overlay = Overlay(candidate.get("overlay") or {}, source="canary")

        ptr = load_pointers()
        ptr["canary"] = f"v{int(candidate['generation_id']):03d}"
        save_pointers(ptr)
        if self.agent and getattr(self.agent, "sovereign", None):
            try:
                self.agent.sovereign.lifecycle.start_canary(candidate["generation_id"])
                self.agent.sovereign.state.set_mode("canary")
            except Exception:
                pass

        activate(cand_overlay)
        set_overlay(cand_overlay.data)
        try:
            cand_run = run_suite(cand_overlay.data, wrapped, include_capability=True)
            activate(baseline_overlay)
            set_overlay(baseline_overlay.data)
            base_run = run_suite(baseline_overlay.data, wrapped, include_capability=True)
        finally:
            # leave candidate staged only if it passed; otherwise restore previous
            activate(previous)
            set_overlay(previous.data)

        # critical canary tasks that LKG already passes must still pass
        base_ok = {c["name"]: c["ok"] for c in base_run.get("cases") or []}
        failed = []
        for c in cand_run.get("cases") or []:
            if c.get("critical") and base_ok.get(c["name"]) and not c.get("ok"):
                failed.append(c["name"])
            if c.get("category") == "canary" and c.get("critical") and not c.get("ok"):
                if c["name"] not in failed and base_ok.get(c["name"], True):
                    failed.append(c["name"])

        tests_ok = cand_run.get("tests_pass", True) if "tests_pass" in cand_run else not cand_run.get("critical_regressions")
        passed = bool(tests_ok) and not failed and cand_run.get("passed", 0) >= 1
        # if candidate enables new features, extra canary cases may fail on baseline
        # that's fine — only punish regressions vs baseline success
        if failed:
            passed = False

        record = {
            "passed": passed,
            "failed_cases": failed,
            "candidate": {
                "score": cand_run.get("score"),
                "passed": cand_run.get("passed"),
                "total": cand_run.get("total"),
                "latency_ms": cand_run.get("latency_ms"),
            },
            "baseline": {
                "score": base_run.get("score"),
                "passed": base_run.get("passed"),
                "total": base_run.get("total"),
                "latency_ms": base_run.get("latency_ms"),
            },
            "started_at": datetime.now().isoformat(),
            "mock": False,
        }

        release = Path(candidate.get("release_dir") or release_path(candidate["generation_id"]))
        (release / "canary").mkdir(parents=True, exist_ok=True)
        (release / "canary" / "canary_result.json").write_text(json.dumps(record, indent=2))
        candidate["canary_results"] = record

        if self.agent and getattr(self.agent, "sovereign", None):
            try:
                self.agent.sovereign.lifecycle.end_canary(passed)
            except Exception:
                pass

        if not passed:
            ptr = load_pointers()
            ptr["canary"] = None
            save_pointers(ptr)
        return record
