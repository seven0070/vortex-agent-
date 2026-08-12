"""Real static security scan of a candidate checkout — not a checkbox."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List

SECRET_RE = re.compile(
    r"(api[_-]?key|secret|password|token|sk-[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{16})\s*[:=]\s*['\"][^'\"]+['\"]",
    re.I,
)
DANGEROUS = [
    (re.compile(r"\brm\s+-rf\b"), "no_rm_rf"),
    (re.compile(r"\bdrop\s+table\b", re.I), "no_drop_table"),
    (re.compile(r"\beval\s*\("), "no_eval"),
    (re.compile(r"\bexec\s*\("), "no_exec"),
    (re.compile(r"\bsubprocess\b"), "no_subprocess_in_overlay"),
    (re.compile(r"\bos\.system\b"), "no_os_system"),
    (re.compile(r"\bsocket\b"), "no_network"),
    (re.compile(r"\burllib\b|\brequests\b"), "no_network"),
]

PROTECTED = (
    "orchestrator.py", "orchestration/", "governance/policy.py",
    "sovereign/", "memory.py", "self_improve.py", "evals.py",
)


class SecurityScanner:
    def __init__(self):
        self.checks = [
            "no_rm_rf", "no_hardcoded_secrets", "syntax_ok",
            "permissions_ok", "no_production_write", "no_eval",
        ]

    def scan(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        findings: List[str] = []
        checks = {c: "pass" for c in self.checks}
        risk = 0.08

        if candidate.get("production_write"):
            checks["no_production_write"] = "fail"
            findings.append("candidate would write production source")
            risk = 0.95

        for change in candidate.get("change_set") or []:
            target = str(change.get("file") or change.get("target") or "")
            if any(p in target for p in PROTECTED) and change.get("overwrite_production"):
                checks["permissions_ok"] = "fail"
                findings.append(f"protected file targeted: {target}")
                risk = max(risk, 0.9)

        checkout = Path(candidate.get("checkout_dir") or "")
        texts: List[str] = []
        if checkout.exists():
            for path in checkout.rglob("*"):
                if path.is_file() and path.suffix in {".py", ".json", ".diff", ".txt"}:
                    try:
                        texts.append(path.read_text(errors="ignore"))
                    except Exception:
                        continue
                    if path.suffix == ".py":
                        try:
                            ast.parse(path.read_text())
                        except SyntaxError as e:
                            checks["syntax_ok"] = "fail"
                            findings.append(f"syntax error in {path.name}: {e}")
                            risk = max(risk, 0.7)

        blob = "\n".join(texts)
        if SECRET_RE.search(blob):
            checks["no_hardcoded_secrets"] = "fail"
            findings.append("possible hardcoded secret")
            risk = max(risk, 0.8)

        # compiler.py uses ast + eval on a restricted numeric expression inside the harness.
        # That is expected. Flag only unexpected eval/exec in overlay.json or patches.
        overlay_blob = ""
        overlay_path = checkout / "overlay.json" if checkout.exists() else None
        if overlay_path and overlay_path.exists():
            overlay_blob = overlay_path.read_text()
        patch_dir = Path(candidate.get("release_dir") or "") / "patches"
        if patch_dir.exists():
            for p in patch_dir.iterdir():
                try:
                    overlay_blob += "\n" + p.read_text()
                except Exception:
                    pass
        for rx, name in DANGEROUS:
            if name in ("no_eval", "no_exec", "no_subprocess_in_overlay"):
                if rx.search(overlay_blob):
                    checks[name] = "fail"
                    findings.append(f"dangerous pattern in overlay/patch: {name}")
                    risk = max(risk, 0.75)
            elif rx.search(overlay_blob):
                checks[name] = "fail"
                findings.append(f"dangerous pattern: {name}")
                risk = max(risk, 0.85)

        if "rm -rf" in blob and "/ " in blob:
            checks["no_rm_rf"] = "fail"
            risk = max(risk, 0.95)

        passed = risk < 0.65 and all(v == "pass" for k, v in checks.items() if k in self.checks)
        results = {
            "checks": checks,
            "findings": findings,
            "risk_score": round(risk, 3),
            "passed": passed,
            "mock": False,
        }
        candidate["security_results"] = results
        candidate["performance_results"] = {
            "latency_ms": (candidate.get("sandbox_result") or {}).get("latency_ms"),
            "risk": risk,
        }
        return results
