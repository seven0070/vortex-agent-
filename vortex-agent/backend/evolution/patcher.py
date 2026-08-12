"""
Apply a real code/data change to an isolated candidate checkout.

Never writes into production backend/*.py. The checkout is a self-contained
directory under releases/vXXX/.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .compiler import default_overlay
from .overlay import Overlay, next_generation_id, release_path, releases_dir


HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "tests" / "fixtures" / "golden_tasks.json"


class CandidatePatcher:
    """Copy evolvable modules into a versioned checkout and apply a concrete overlay patch."""

    def __init__(self, memory=None, base_path: Path = None):
        self.memory = memory
        self.base = base_path or releases_dir()
        self.base.mkdir(parents=True, exist_ok=True)

    def create_candidate(self, parent_generation: int, hypothesis: Dict[str, Any],
                         change_set: List[Dict], parent_overlay: Overlay = None) -> Dict[str, Any]:
        gen_id = next_generation_id(self.memory)
        release_dir = self.base / f"v{gen_id:03d}"
        if release_dir.exists():
            gen_id = max(gen_id, parent_generation + 1)
            release_dir = self.base / f"v{gen_id:03d}"
        checkout = release_dir / "checkout"
        patches = release_dir / "patches"
        golden = release_dir / "golden"
        for d in (checkout, patches, golden, release_dir / "benchmarks", release_dir / "canary"):
            d.mkdir(parents=True, exist_ok=True)

        parent_overlay = parent_overlay or Overlay.genesis()
        new_overlay = parent_overlay.copy()
        new_overlay.data["generation_id"] = gen_id
        new_overlay.data["parent_generation"] = parent_generation
        applied = self._apply_hypothesis(new_overlay, hypothesis, change_set)

        # isolated copies the candidate actually executes
        shutil.copy2(HERE / "compiler.py", checkout / "compiler.py")
        shutil.copy2(HERE / "harness.py", checkout / "harness.py")
        new_overlay.dump(checkout / "overlay.json")
        new_overlay.dump(release_dir / "overlay.json")
        if FIXTURES.exists():
            shutil.copy2(FIXTURES, checkout / "fixtures.json")
            shutil.copy2(FIXTURES, release_dir / "fixtures.json")
        else:
            (checkout / "fixtures.json").write_text(json.dumps({"regression": [], "capability": []}))

        diff_lines = [
            f"--- parent overlay gen {parent_generation}",
            f"+++ candidate overlay gen {gen_id}",
            f"@@ hypothesis: {hypothesis.get('hypothesis', '')}",
        ]
        for item in applied:
            diff_lines.append(f"+ {item}")
        diff_text = "\n".join(diff_lines) + "\n"
        (patches / "applied.diff").write_text(diff_text)
        (patches / "change_set.json").write_text(json.dumps(change_set, indent=2))

        router_raw = "{}"
        try:
            if self.memory:
                router_raw = self.memory.get_kv("rsi_router") or "{}"
        except Exception:
            router_raw = "{}"
        (release_dir / "router_snapshot.json").write_text(router_raw)

        candidate = {
            "generation_id": gen_id,
            "parent_generation": parent_generation,
            "hypothesis": hypothesis,
            "change_set": change_set,
            "applied_patches": applied,
            "release_dir": str(release_dir),
            "checkout_dir": str(checkout),
            "overlay": new_overlay.data,
            "patch_diff": diff_text,
            "created_at": datetime.now().isoformat(),
            "status": "patched",
            "production_write": False,
        }
        (release_dir / "candidate.json").write_text(json.dumps(self._jsonable(candidate), indent=2))
        return candidate

    def _apply_hypothesis(self, overlay: Overlay, hypothesis: Dict[str, Any],
                          change_set: List[Dict]) -> List[str]:
        applied: List[str] = []
        types = [c.get("type") for c in (change_set or [])]
        target = ""
        if change_set:
            target = str(change_set[0].get("target") or "")
        hyp = (hypothesis or {}).get("hypothesis", "")
        compiler = overlay.data.setdefault("compiler", {})
        want_compiler = (
            "compiler_improve" in types
            or "eval_failure" in types
            or "chain" in hyp.lower()
            or "reasoning-chain" in target
            or "compiler" in hyp.lower()
            or not types
        )
        if want_compiler:
            if not compiler.get("chained_arithmetic"):
                compiler["chained_arithmetic"] = True
                applied.append("compiler.chained_arithmetic = true")
            if not compiler.get("power_operator"):
                compiler["power_operator"] = True
                applied.append("compiler.power_operator = true")
        if "router_improve" in types or "router_boost" in types:
            boosts = overlay.data.setdefault("router_boosts", {})
            key = target or "codeforge"
            bucket = boosts.setdefault(key, {})
            bucket["tool:codeforge"] = round(float(bucket.get("tool:codeforge", 0.0)) + 1.5, 3)
            applied.append(f"router_boosts[{key}].tool:codeforge += 1.5")
        if "retry_improve" in types:
            retry = overlay.data.setdefault("retry", {})
            retry["codeforge_eval_expr"] = True
            retry["codeforge_wrap_print"] = True
            applied.append("retry.codeforge_eval_expr = true")
        if "lesson_tune" in types:
            overlay.data.setdefault("intent_rules", []).append({
                "name": f"tune_{target or 'general'}",
                "trigger": target or "general",
                "tool": "codeforge",
            })
            applied.append(f"intent_rules += tune_{target or 'general'}")
        if not applied:
            # still a real file-level change so the candidate is not metadata-only
            compiler["chained_arithmetic"] = True
            compiler["power_operator"] = True
            applied.append("compiler.chained_arithmetic = true (fallback real patch)")
            applied.append("compiler.power_operator = true (fallback real patch)")
        overlay.data["patched_at"] = datetime.now().isoformat()
        overlay.data["applied_patches"] = applied
        return applied

    @staticmethod
    def _jsonable(obj):
        try:
            json.dumps(obj)
            return obj
        except TypeError:
            return json.loads(json.dumps(obj, default=str))


# backward-compatible name used by older docs
CandidateGenerator = CandidatePatcher
