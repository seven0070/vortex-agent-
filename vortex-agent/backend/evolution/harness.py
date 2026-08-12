"""
Isolated candidate harness.

Copied into a release checkout and executed with `python -I` so the candidate
is judged by its own overlay, not production code.
"""
from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from compiler import compile_any, compile_math, compile_fib, set_overlay  # noqa: E402


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return default
    return default


def _eval_print_expr(code: str):
    tree = ast.parse(code)
    body = tree.body
    if len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Call):
        call = body[0].value
        if getattr(call.func, "id", None) == "print" and call.args:
            return eval(compile(ast.Expression(call.args[0]), "<overlay>", "eval"), {"__builtins__": {}}, {})
    if "def fib" in code:
        ns = {}
        exec(code.replace("print(", "_result = (") if False else code, ns, ns)
        # fib files end with print(fib(n)); execute safely
        local = {}
        exec(compile(code, "<fib>", "exec"), {"__builtins__": {"range": range, "print": lambda x: local.setdefault("out", x)}}, local)
        return local.get("out")
    return None


def _safe_value(code: str):
    try:
        if code.strip().startswith("def fib"):
            local = {}

            def _capture(x):
                local["out"] = x

            exec(compile(code, "<fib>", "exec"), {"__builtins__": {"range": range, "print": _capture}}, local)
            return local.get("out")
        tree = ast.parse(code)
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Call):
            call = tree.body[0].value
            if getattr(call.func, "id", None) == "print" and call.args:
                return eval(
                    compile(ast.Expression(call.args[0]), "<overlay>", "eval"),
                    {"__builtins__": {}},
                    {},
                )
    except Exception:
        return None
    return None


def run_suite(overlay: dict, fixtures: dict, include_capability: bool = True) -> dict:
    prev = None
    try:
        from compiler import current_overlay
        prev = current_overlay()
    except Exception:
        prev = None
    set_overlay(overlay)
    try:
        return _run_suite_body(overlay, fixtures, include_capability)
    finally:
        set_overlay(prev)


def _run_suite_body(overlay: dict, fixtures: dict, include_capability: bool = True) -> dict:
    compiler = overlay.get("compiler") or {}
    cases = list(fixtures.get("regression") or [])
    if include_capability:
        cases.extend(fixtures.get("capability") or [])
    results = []
    passed = 0
    total_w = 0.0
    earned = 0.0
    regressions = []
    critical_regressions = []
    t0 = time.time()
    for case in cases:
        requires = case.get("requires")
        if requires and not compiler.get(requires):
            ok = False
            code = compile_any(case["message"])
            value = _safe_value(code) if code else None
            note = f"feature {requires} disabled"
        else:
            code = compile_any(case["message"])
            value = _safe_value(code) if code else None
            expect_code = case.get("expect_code")
            expect_value = case.get("expect_value")
            ok_code = bool(code) and (not expect_code or expect_code in code)
            ok_val = True
            if expect_value is not None:
                ok_val = str(value) == str(expect_value)
            ok = bool(ok_code and ok_val)
            note = "ok" if ok else f"code={code!r} value={value!r}"
        w = float(case.get("weight", 1.0))
        total_w += w
        if ok:
            passed += 1
            earned += w
        else:
            if case.get("category") == "regression" or case.get("critical"):
                regressions.append(case["name"])
                if case.get("critical") and case.get("category") == "regression":
                    critical_regressions.append(case["name"])
        results.append({
            "name": case["name"],
            "category": case.get("category"),
            "ok": ok,
            "weight": w,
            "note": note,
            "critical": bool(case.get("critical")),
        })
    latency_ms = int((time.time() - t0) * 1000)
    score = round(earned / total_w, 4) if total_w else 0.0
    return {
        "passed": passed,
        "total": len(cases),
        "score": score,
        "quality": score,
        "reliability": round(passed / len(cases), 4) if cases else 0.0,
        "latency_ms": latency_ms,
        "cost": float(len(cases)),
        "regressions": regressions,
        "critical_regressions": critical_regressions,
        "cases": results,
        "mock": False,
        "tests_pass": not critical_regressions,
    }


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    overlay_path = HERE / "overlay.json"
    fixtures_path = HERE / "fixtures.json"
    out_path = HERE / "sandbox_result.json"
    include_capability = True
    i = 0
    while i < len(argv):
        if argv[i] == "--overlay" and i + 1 < len(argv):
            overlay_path = Path(argv[i + 1])
            i += 2
        elif argv[i] == "--fixtures" and i + 1 < len(argv):
            fixtures_path = Path(argv[i + 1])
            i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out_path = Path(argv[i + 1])
            i += 2
        elif argv[i] == "--regression-only":
            include_capability = False
            i += 1
        else:
            i += 1
    overlay = _load_json(overlay_path, {})
    set_overlay(overlay)
    fixtures = _load_json(fixtures_path, {"regression": [], "capability": []})
    syntax_ok = True
    syntax_error = None
    try:
        ast.parse((HERE / "compiler.py").read_text())
    except Exception as e:
        syntax_ok = False
        syntax_error = str(e)
    result = run_suite(overlay, fixtures, include_capability=include_capability)
    result["syntax_ok"] = syntax_ok
    result["syntax_error"] = syntax_error
    result["tests_pass"] = bool(syntax_ok and not result["critical_regressions"])
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return 0 if result["tests_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
