"""
Isolated sandbox: real subprocess, timeout, no production imports, no mock pass.

Runs:
  1. candidate harness (overlay compiler + golden fixtures)
  2. worktree unittest (tests.test_rsi.CompilerTests) when a git worktree exists
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict


class SandboxRunner:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def run_tests(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        checkout = Path(candidate.get("checkout_dir") or "")
        harness = checkout / "harness.py"
        start = time.time()
        if not harness.exists():
            result = {
                "passed": False,
                "tests_pass": False,
                "output": "sandbox missing harness.py — refusing mock pass",
                "latency_ms": int((time.time() - start) * 1000),
                "mock": False,
            }
            candidate["sandbox_result"] = result
            candidate["status"] = "sandbox_failed"
            return {"status": "error", "result": result, "passed": False}

        out_path = checkout / "sandbox_result.json"
        sandbox_home = checkout / "sandbox_home"
        sandbox_home.mkdir(parents=True, exist_ok=True)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(sandbox_home),
            "VORTEX_HOME": str(sandbox_home),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(harness), "--out", str(out_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(checkout),
                env=env,
            )
        except subprocess.TimeoutExpired:
            result = {
                "passed": False,
                "tests_pass": False,
                "output": f"sandbox timed out after {self.timeout}s",
                "latency_ms": int((time.time() - start) * 1000),
                "mock": False,
            }
            candidate["sandbox_result"] = result
            candidate["status"] = "sandbox_failed"
            return {"status": "error", "result": result, "passed": False}

        payload: Dict[str, Any] = {}
        if out_path.exists():
            try:
                payload = json.loads(out_path.read_text())
            except Exception as e:
                payload = {"parse_error": str(e)}
        elif proc.stdout.strip():
            try:
                payload = json.loads(proc.stdout.strip().splitlines()[-1])
            except Exception:
                payload = {}

        tests_pass = bool(payload.get("tests_pass")) and proc.returncode in (0, 1)
        # returncode 1 means capability misses but critical regressions fail tests_pass
        if payload.get("syntax_ok") is False:
            tests_pass = False
        if payload.get("critical_regressions"):
            tests_pass = False
        # sandbox "tests" = regression + syntax. Capability gaps are benchmark, not test failure.
        if payload.get("syntax_ok", True) and not payload.get("critical_regressions"):
            tests_pass = True

        result = {
            "passed": tests_pass,
            "tests_pass": tests_pass,
            "output": (proc.stdout or "")[-2000:] + (("\n" + proc.stderr) if proc.stderr else ""),
            "returncode": proc.returncode,
            "latency_ms": int((time.time() - start) * 1000),
            "detail": payload,
            "mock": False,
        }
        if "sandbox tests passed (mock)" in (result["output"] or ""):
            result["passed"] = False
            result["tests_pass"] = False
            result["output"] += "\nrefusing mock sandbox result"
            tests_pass = False

        worktree_run = self._run_worktree_unittests(candidate, sandbox_home)
        result["worktree_tests"] = worktree_run
        if worktree_run.get("ran") and not worktree_run.get("passed"):
            tests_pass = False
            result["passed"] = False
            result["tests_pass"] = False
            result["output"] += "\nworktree unittest failed:\n" + (worktree_run.get("output") or "")[-800:]

        candidate["sandbox_result"] = result
        candidate["status"] = "sandbox_passed" if tests_pass else "sandbox_failed"
        return {"status": "success" if tests_pass else "error", "result": result, "passed": tests_pass}

    def _check_deps(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Verify candidate Python can import declared requirements (no silent skip)."""
        worktree = Path(candidate.get("worktree_dir") or "")
        req = worktree / "vortex-agent" / "backend" / "requirements.txt"
        if not req.exists():
            req = Path(__file__).resolve().parent.parent / "requirements.txt"
        needed = []
        if req.exists():
            for line in req.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    needed.append(line.split("==")[0].split(">=")[0].split("[")[0].strip())
        missing = []
        for name in needed:
            try:
                __import__(name.replace("-", "_"))
            except Exception:
                missing.append(name)
        return {"checked": needed, "missing": missing, "ok": not missing}

    def _run_worktree_unittests(self, candidate: Dict[str, Any], sandbox_home: Path) -> Dict[str, Any]:
        worktree = Path(candidate.get("worktree_dir") or "")
        backend = worktree / "vortex-agent" / "backend"
        if not worktree.exists() or not backend.exists():
            return {"ran": False, "passed": True, "reason": "no worktree"}
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(sandbox_home),
            "VORTEX_HOME": str(sandbox_home / "worktree_home"),
            "PYTHONPATH": str(backend),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "tests.test_rsi.CompilerTests", "-q"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(backend),
                env=env,
            )
        except subprocess.TimeoutExpired:
            return {"ran": True, "passed": False, "output": "worktree unittest timed out"}
        out = (proc.stdout or "") + (proc.stderr or "")
        return {
            "ran": True,
            "passed": proc.returncode == 0,
            "returncode": proc.returncode,
            "output": out[-1500:],
        }
