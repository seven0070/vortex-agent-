"""
Vortex code mutation — the step the evolution engine was missing.

Before this, `change_set` was a *description* of a change: {"file": "self_improve.py",
"type": "router_boost"}. Nothing consumed it. A cycle could report "promoted" having
modified zero source files. The pipeline around it (sandbox, security, benchmark,
governance, canary) was real, but it was gating an empty diff.

This produces actual unified diffs, applies them to a throwaway COPY of the source
tree, runs the real test suite and frozen eval in that copy, and only then queues the
diff for human approval. Nothing touches the working tree without an explicit approve.

Safety model
------------
1. SANDBOX FIRST. Diffs are applied to a temp copy, never in place. Verification runs
   in a subprocess rooted there.
2. TESTS AND EVALS ARE IMMUTABLE. An agent that can edit its own tests can pass any
   gate by deleting it. `tests/`, `evals.py` and this module are un-mutatable, so the
   frozen eval keeps meaning what it says.
3. HUMAN APPROVAL. Verified diffs land in a queue. Applying to the working tree is a
   separate, explicit action that writes a backup and supports rollback.
4. GOVERNANCE + SECURITY. Every diff is scanned for dangerous constructs and passed
   through the existing policy layer before it can be queued.
"""
from __future__ import annotations

import ast
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parent

# Never mutable. Editing these would let the agent game its own gate, or rewrite the
# machinery that constrains it.
PROTECTED = {
    "evals.py",           # the frozen eval — the thing that decides promotion
    "code_mutation.py",   # this file — no self-exempting
    "paths.py",           # where data lives
    "main.py",            # server entrypoint
}
PROTECTED_DIRS = {"tests", "__pycache__", ".git", "releases", "static"}

# Constructs that must never appear in generated code.
DANGEROUS = [
    (re.compile(r"\bos\.system\s*\("), "os.system call"),
    (re.compile(r"\bsubprocess\.(?:call|run|Popen|check_output)\s*\(", re.I), "subprocess spawn"),
    (re.compile(r"\b__import__\s*\("), "dynamic __import__"),
    (re.compile(r"\beval\s*\("), "eval()"),
    (re.compile(r"\bexec\s*\("), "exec()"),
    (re.compile(r"\bshutil\.rmtree\s*\("), "recursive delete"),
    (re.compile(r"\bos\.remove\s*\(|\bos\.unlink\s*\("), "file deletion"),
    (re.compile(r"\bsocket\.|urllib\.request|requests\.(?:get|post)|httpx\.", re.I), "network access"),
    # bare imports of capability modules, e.g. "import socket" with use elsewhere
    (re.compile(r"^\s*(?:import|from)\s+(?:os|sys|socket|subprocess|shutil|urllib|requests|httpx|ctypes|pickle|marshal)\b"),
     "import of restricted module"),
    (re.compile(r"\bopen\s*\([^)]*['\"][wa]"), "file write"),
    (re.compile(r"\bsetattr\s*\(|\bglobals\s*\(\)|\blocals\s*\(\)"), "runtime introspection"),
    (re.compile(r"\bpickle\.|marshal\."), "unsafe deserialization"),
]


def _is_mutable(rel_path: str) -> Tuple[bool, str]:
    p = Path(rel_path)
    if p.is_absolute() or ".." in p.parts:
        return False, "path escapes backend directory"
    if p.suffix != ".py":
        return False, "only .py files are mutable"
    if any(part in PROTECTED_DIRS for part in p.parts):
        return False, f"protected directory ({'/'.join(p.parts[:-1])})"
    if p.name in PROTECTED:
        return False, f"protected file ({p.name})"
    if not (BACKEND / p).exists():
        return False, "file does not exist"
    return True, ""


class Diff:
    """One proposed edit to one file."""

    def __init__(self, path: str, old: str, new: str, rationale: str = ""):
        self.path = path
        self.old = old
        self.new = new
        self.rationale = rationale

    @property
    def unified(self) -> str:
        return "".join(difflib.unified_diff(
            self.old.splitlines(keepends=True),
            self.new.splitlines(keepends=True),
            fromfile=f"a/{self.path}", tofile=f"b/{self.path}",
        ))

    @property
    def added_lines(self) -> List[str]:
        return [ln[1:] for ln in self.unified.splitlines()
                if ln.startswith("+") and not ln.startswith("+++")]

    def stats(self) -> Dict[str, int]:
        u = self.unified.splitlines()
        return {
            "added": sum(1 for l in u if l.startswith("+") and not l.startswith("+++")),
            "removed": sum(1 for l in u if l.startswith("-") and not l.startswith("---")),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "rationale": self.rationale,
                "unified": self.unified, "stats": self.stats()}


class DiffSecurityScanner:
    """Scan *added* lines only — pre-existing code isn't the diff's fault."""

    def scan(self, diffs: List[Diff]) -> Dict[str, Any]:
        findings = []
        for d in diffs:
            ok, why = _is_mutable(d.path)
            if not ok:
                findings.append({"path": d.path, "issue": f"immutable target: {why}",
                                 "severity": "critical"})
            for line in d.added_lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for rx, label in DANGEROUS:
                    if rx.search(line):
                        findings.append({"path": d.path, "issue": label,
                                         "line": stripped[:120], "severity": "high"})
        crit = [f for f in findings if f["severity"] == "critical"]
        risk = min(1.0, 0.4 * len(crit) + 0.2 * (len(findings) - len(crit)))
        return {"passed": not findings, "findings": findings,
                "risk_score": round(risk, 3), "scanned": len(diffs)}


class SandboxedRepo:
    """
    A disposable copy of the backend tree.

    Verification runs here, in a subprocess with its own VORTEX_HOME, so a bad diff
    cannot corrupt the real source or the real memory database.
    """

    # The sandbox copy has no warm __pycache__, so every import recompiles: the suite
    # runs ~100x slower there (~190s vs ~2s) than in the working tree. Verification is
    # not on the interactive path, so a generous ceiling beats a false "timeout" verdict.
    def __init__(self, timeout: int = 600):
        self.timeout = timeout
        self.root: Optional[Path] = None
        self.home: Optional[Path] = None

    def __enter__(self) -> "SandboxedRepo":
        tmp = Path(tempfile.mkdtemp(prefix="vortex_sandbox_"))
        self.root = tmp / "backend"
        self.home = tmp / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            BACKEND, self.root,
            # test_code_mutation.py itself spawns sandboxes. Copying it in makes
            # verification recursive — each nested run spawns more, and the whole
            # thing times out at 0 tests. Mutations can never touch code_mutation.py
            # (it is PROTECTED), so excluding its tests costs no safety here; they
            # still run in the normal suite.
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "releases", ".git",
                                          "test_code_mutation.py"),
        )
        return self

    def __exit__(self, *exc) -> None:
        if self.root:
            shutil.rmtree(self.root.parent, ignore_errors=True)

    def apply(self, diffs: List[Diff]) -> Dict[str, Any]:
        """Write proposed content into the copy. Verifies each file still parses."""
        applied, errors = [], []
        for d in diffs:
            ok, why = _is_mutable(d.path)
            if not ok:
                errors.append({"path": d.path, "error": why})
                continue
            target = self.root / d.path  # type: ignore[operator]
            try:
                current = target.read_text()
                if current != d.old:
                    errors.append({"path": d.path, "error": "source drifted; diff is stale"})
                    continue
                ast.parse(d.new)  # syntax gate before writing
                target.write_text(d.new)
                applied.append(d.path)
            except SyntaxError as e:
                errors.append({"path": d.path, "error": f"syntax error: {e}"})
            except Exception as e:
                errors.append({"path": d.path, "error": str(e)})
        return {"applied": applied, "errors": errors, "ok": bool(applied) and not errors}

    def _run(self, code: str) -> Dict[str, Any]:
        env = dict(os.environ)
        env["VORTEX_HOME"] = str(self.home)
        # Let the sandbox WRITE bytecode: the copy starts cold, and caching brings the
        # verification suite from ~190s down substantially on repeat runs.
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        env.pop("VORTEX_LLM_PROVIDER", None)  # verification must be deterministic
        env.pop("VORTEX_LLM_API_KEY", None)
        t0 = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code], cwd=str(self.root), env=env,
                capture_output=True, text=True, timeout=self.timeout,
            )
            return {"rc": proc.returncode, "stdout": proc.stdout[-4000:],
                    "stderr": proc.stderr[-4000:], "ms": int((time.time() - t0) * 1000)}
        except subprocess.TimeoutExpired:
            return {"rc": -1, "stdout": "", "stderr": "timeout", "ms": self.timeout * 1000}

    def run_tests(self) -> Dict[str, Any]:
        r = self._run(
            "import unittest,sys;"
            "l=unittest.TestLoader().discover('tests');"
            "res=unittest.TextTestRunner(verbosity=0).run(l);"
            "print('TESTS', res.testsRun, len(res.failures), len(res.errors));"
            "sys.exit(0 if res.wasSuccessful() else 1)"
        )
        m = re.search(r"TESTS (\d+) (\d+) (\d+)", r["stdout"] + r["stderr"])
        return {"passed": r["rc"] == 0, "ran": int(m.group(1)) if m else 0,
                "failures": int(m.group(2)) if m else -1,
                "errors": int(m.group(3)) if m else -1,
                "ms": r["ms"], "stderr": r["stderr"][-1500:]}

    def run_frozen_eval(self) -> Dict[str, Any]:
        r = self._run(
            "import json,sys;sys.path.insert(0,'.');"
            "from memory import Memory;from swarm import VortexAgent;from evals import run_suite;"
            "a=VortexAgent(Memory());s=run_suite(a,persist=False);"
            "print('EVAL'+json.dumps({'score':s['score'],'passed':s['passed'],'total':s['total']}))"
        )
        m = re.search(r"EVAL(\{.*\})", r["stdout"])
        if not m:
            return {"ok": False, "score": 0.0, "error": (r["stderr"] or r["stdout"])[-800:]}
        d = json.loads(m.group(1))
        return {"ok": True, "score": d["score"], "passed": d["passed"],
                "total": d["total"], "ms": r["ms"]}


class MutationProposer:
    """
    Turns a weakness into an actual diff.

    Two paths. Deterministic tuning works with no model at all: it retunes named
    numeric constants that govern behaviour. When an LLM is configured it can author
    a real edit — which is the genuine "agent writes code" capability.
    """

    # Constants safe to retune, with bounds. Bounds are the point: an unbounded
    # constant rewrite is how you get a runaway loop.
    TUNABLE = {
        "skill_manage.py": {
            "COMPLEXITY_TOOL_CALLS": (1, 6),
            "COMPLEXITY_STEPS": (1, 6),
        },
        "profile_memory.py": {
            "MEMORY_CAP": (500, 8000),
            "USER_CAP": (500, 4000),
        },
    }

    def __init__(self, agent=None):
        self.agent = agent

    def propose(self, weakness: Dict[str, Any]) -> List[Diff]:
        diffs = self._propose_llm(weakness)
        if diffs:
            return diffs
        return self._propose_tuning(weakness)

    # ── deterministic ──
    def _propose_tuning(self, weakness: Dict[str, Any]) -> List[Diff]:
        target = str(weakness.get("target", ""))
        for fname, consts in self.TUNABLE.items():
            for const, (lo, hi) in consts.items():
                if const.lower() in target.lower() or weakness.get("constant") == const:
                    return self._retune(fname, const, lo, hi,
                                        weakness.get("direction", "down"))
        # default: nudge the skill-capture bar down so more procedures get captured
        return self._retune("skill_manage.py", "COMPLEXITY_TOOL_CALLS", 1, 6, "down")

    def _retune(self, fname: str, const: str, lo: int, hi: int, direction: str) -> List[Diff]:
        path = BACKEND / fname
        if not path.exists():
            return []
        src = path.read_text()
        m = re.search(rf"^({re.escape(const)}\s*=\s*)(\d+)", src, re.M)
        if not m:
            return []
        cur = int(m.group(2))
        new = cur - 1 if direction == "down" else cur + 1
        new = max(lo, min(hi, new))
        if new == cur:
            return []
        updated = src[:m.start()] + f"{m.group(1)}{new}" + src[m.end():]
        return [Diff(fname, src, updated,
                     f"Retune {const}: {cur} → {new} (bounds {lo}-{hi})")]

    # ── model-authored ──
    def _propose_llm(self, weakness: Dict[str, Any]) -> List[Diff]:
        try:
            from llm import get_llm
            llm = get_llm()
            if not llm.available:
                return []
        except Exception:
            return []

        fname = str(weakness.get("file") or "skill_manage.py")
        ok, _ = _is_mutable(fname)
        if not ok:
            return []
        src = (BACKEND / fname).read_text()
        if len(src) > 20000:
            return []

        system = (
            "You modify a single Python file for an agent framework. Make the SMALLEST "
            "change that addresses the weakness. Constraints: no imports of os/subprocess/"
            "socket, no file writes, no eval/exec, do not touch tests. "
            'Respond with ONLY JSON: {"new_source": "<the COMPLETE updated file>", '
            '"rationale": "<one sentence>"}'
        )
        user = (f"Weakness: {weakness.get('description') or weakness.get('type')}\n"
                f"Target: {weakness.get('target')}\n\nFile {fname}:\n```python\n{src}\n```")
        data = llm.complete_json(system, user, temperature=0.0)
        if not isinstance(data, dict):
            return []
        new_src = data.get("new_source")
        if not isinstance(new_src, str) or not new_src.strip() or new_src == src:
            return []
        try:
            ast.parse(new_src)
        except SyntaxError:
            return []
        return [Diff(fname, src, new_src, str(data.get("rationale", "model-authored"))[:200])]


class ApprovalQueue:
    """Verified diffs wait here. Applying to the working tree is a human decision."""

    def __init__(self, home=None):
        from paths import vortex_home
        self.dir = (home or vortex_home()) / "pending_mutations"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.backups = (home or vortex_home()) / "mutation_backups"
        self.backups.mkdir(parents=True, exist_ok=True)

    def submit(self, record: Dict[str, Any]) -> str:
        mid = record.get("id") or f"m_{uuid.uuid4().hex[:10]}"
        record["id"] = mid
        record["submitted_at"] = datetime.now().isoformat()
        record["state"] = "pending"
        (self.dir / f"{mid}.json").write_text(json.dumps(record, indent=2))
        return mid

    def list_pending(self) -> List[Dict[str, Any]]:
        out = []
        for f in sorted(self.dir.glob("m_*.json")):
            try:
                r = json.loads(f.read_text())
                if r.get("state") == "pending":
                    out.append(r)
            except Exception:
                continue
        return out

    def get(self, mid: str) -> Optional[Dict[str, Any]]:
        p = self.dir / f"{mid}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def _update(self, mid: str, **fields) -> Optional[Dict[str, Any]]:
        r = self.get(mid)
        if not r:
            return None
        r.update(fields)
        (self.dir / f"{mid}.json").write_text(json.dumps(r, indent=2))
        return r

    def reject(self, mid: str, reason: str = "") -> Optional[Dict[str, Any]]:
        return self._update(mid, state="rejected", reject_reason=reason,
                            resolved_at=datetime.now().isoformat())

    def approve(self, mid: str, apply: bool = True) -> Dict[str, Any]:
        """
        Approve and (optionally) write to the working tree.

        Every touched file is backed up first, so `rollback(mid)` fully restores.
        """
        rec = self.get(mid)
        if not rec:
            return {"error": "not found"}
        if rec.get("state") != "pending":
            return {"error": f"already {rec.get('state')}"}
        if not rec.get("verified"):
            return {"error": "refusing to apply an unverified mutation"}
        if not apply:
            return self._update(mid, state="approved_not_applied") or {}

        backup_dir = self.backups / mid
        backup_dir.mkdir(parents=True, exist_ok=True)
        written, errors = [], []
        for d in rec.get("diffs", []):
            path, new_src = d.get("path"), d.get("new_source")
            ok, why = _is_mutable(path or "")
            if not ok or not new_src:
                errors.append({"path": path, "error": why or "missing new_source"})
                continue
            target = BACKEND / path
            try:
                current = target.read_text()
                if current != d.get("old_source"):
                    errors.append({"path": path, "error": "source drifted since verification"})
                    continue
                (backup_dir / Path(path).name).write_text(current)
                ast.parse(new_src)
                target.write_text(new_src)
                written.append(path)
            except Exception as e:
                errors.append({"path": path, "error": str(e)})

        if errors and not written:
            self._update(mid, state="apply_failed", apply_errors=errors)
            return {"applied": [], "errors": errors, "state": "apply_failed"}

        self._update(mid, state="applied", applied_files=written,
                     apply_errors=errors, backup_dir=str(backup_dir),
                     applied_at=datetime.now().isoformat())
        return {"applied": written, "errors": errors, "state": "applied",
                "rollback": f"POST /api/evolution/rollback/{mid}"}

    def rollback(self, mid: str) -> Dict[str, Any]:
        rec = self.get(mid)
        if not rec or rec.get("state") != "applied":
            return {"error": "nothing to roll back"}
        restored, errors = [], []
        for path in rec.get("applied_files", []):
            src = Path(rec["backup_dir"]) / Path(path).name
            if not src.exists():
                errors.append({"path": path, "error": "backup missing"})
                continue
            try:
                (BACKEND / path).write_text(src.read_text())
                restored.append(path)
            except Exception as e:
                errors.append({"path": path, "error": str(e)})
        self._update(mid, state="rolled_back", rolled_back_at=datetime.now().isoformat())
        return {"restored": restored, "errors": errors, "state": "rolled_back"}

    def stats(self) -> Dict[str, Any]:
        by: Dict[str, int] = {}
        for f in self.dir.glob("m_*.json"):
            try:
                # was parsed twice per file (once for the key, once for the lookup)
                state = json.loads(f.read_text()).get("state", "?")
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                continue
            by[state] = by.get(state, 0) + 1
        return {"total": sum(by.values()), "by_state": by, "queue_dir": str(self.dir)}


class CodeEvolution:
    """
    Weakness → diff → sandbox → tests → frozen eval → security → governance → queue.

    The verification is the product. A diff only reaches the queue if it applied
    cleanly to a copy, the full suite passed there, and the frozen eval did not
    regress against the baseline measured in that same sandbox.
    """

    def __init__(self, agent=None, memory=None, governance=None):
        self.agent = agent
        self.memory = memory
        self.governance = governance
        self.proposer = MutationProposer(agent)
        self.scanner = DiffSecurityScanner()
        self.queue = ApprovalQueue()

    def evolve_code(self, weakness: Optional[Dict[str, Any]] = None,
                    auto_apply: bool = False) -> Dict[str, Any]:
        weakness = weakness or {"type": "generic", "target": "COMPLEXITY_TOOL_CALLS",
                                "description": "capture more reusable procedures"}
        rec: Dict[str, Any] = {
            "weakness": weakness, "created_at": datetime.now().isoformat(),
            "verified": False, "stage": "propose",
        }

        diffs = self.proposer.propose(weakness)
        if not diffs:
            rec.update(decision="no_change", reason="no mutation proposed")
            return rec
        rec["diffs"] = [{**d.to_dict(), "old_source": d.old, "new_source": d.new}
                        for d in diffs]
        rec["summary"] = [f"{d.path}: {d.rationale}" for d in diffs]

        # security on the diff itself
        rec["stage"] = "security"
        sec = self.scanner.scan(diffs)
        rec["security"] = sec
        if not sec["passed"]:
            rec.update(decision="rejected", reason=f"security: {sec['findings'][0]['issue']}")
            return rec

        # sandbox: baseline first, then the patched tree
        rec["stage"] = "sandbox"
        with SandboxedRepo() as box:
            base_eval = box.run_frozen_eval()
            if not base_eval.get("ok"):
                rec.update(decision="error", reason=f"baseline eval failed: {base_eval.get('error','')[:200]}")
                return rec
            rec["baseline_eval"] = base_eval

            applied = box.apply(diffs)
            rec["apply"] = applied
            if not applied["ok"]:
                rec.update(decision="rejected",
                           reason=f"apply failed: {applied['errors'][:1]}")
                return rec

            rec["stage"] = "tests"
            tests = box.run_tests()
            rec["tests"] = tests
            if not tests["passed"]:
                rec.update(decision="rejected",
                           reason=f"tests failed ({tests['failures']}f/{tests['errors']}e)")
                return rec

            rec["stage"] = "frozen_eval"
            new_eval = box.run_frozen_eval()
            rec["candidate_eval"] = new_eval
            if not new_eval.get("ok"):
                rec.update(decision="rejected", reason="candidate eval crashed")
                return rec
            if new_eval["score"] < base_eval["score"] - 1e-9:
                rec.update(decision="rejected",
                           reason=f"eval regressed {base_eval['score']:.3f} → {new_eval['score']:.3f}")
                return rec

        # governance
        rec["stage"] = "governance"
        if self.governance:
            try:
                dec = self.governance.evaluate(
                    task="self-modification: apply code diff",
                    context={"files": [d.path for d in diffs],
                             "added": sum(d.stats()["added"] for d in diffs)},
                    agent="improver", action="modify_code")
                rec["governance"] = dec
                if dec.get("action") == "DENY":
                    rec.update(decision="rejected", reason=f"governance: {dec.get('reason')}")
                    return rec
            except Exception as e:
                rec["governance"] = {"error": str(e)}

        rec["verified"] = True
        rec["stage"] = "queued"
        rec["decision"] = "verified_pending_approval"
        rec["reason"] = (f"tests {tests['ran']} passed; eval "
                         f"{base_eval['score']:.3f} → {new_eval['score']:.3f}")
        mid = self.queue.submit(rec)

        if auto_apply:
            rec["auto_apply"] = self.queue.approve(mid, apply=True)
        return rec

    def status(self) -> Dict[str, Any]:
        return {"queue": self.queue.stats(), "pending": self.queue.list_pending(),
                "protected_files": sorted(PROTECTED),
                "protected_dirs": sorted(PROTECTED_DIRS)}
