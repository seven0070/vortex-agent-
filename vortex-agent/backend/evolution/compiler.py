"""
Evolvable compiler — standalone so a candidate checkout can run it with `python -I`.

Baseline overlay keeps two-operand math only.
Promoted overlays may enable chained arithmetic and power.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

_NUM = r"(-?\d+(?:\.\d+)?)"

MATH_PATTERNS = [
    (re.compile(rf"{_NUM}\s*(?:times|multiplied by|x|\*)\s*{_NUM}", re.I), "*"),
    (re.compile(rf"{_NUM}\s*(?:plus|added to|\+)\s*{_NUM}", re.I), "+"),
    (re.compile(rf"{_NUM}\s*(?:minus|subtracted by|less)\s*{_NUM}", re.I), "-"),
    (re.compile(rf"{_NUM}\s*(?:divided by|over|/)\s*{_NUM}", re.I), "/"),
    (re.compile(rf"(?:sum|add|plus)\s+(?:of\s+)?{_NUM}\s+(?:and|,)\s+{_NUM}", re.I), "+"),
    (re.compile(rf"(?:product|multiply)\s+(?:of\s+)?{_NUM}\s+(?:and|,)\s+{_NUM}", re.I), "*"),
    (re.compile(rf"(?:difference|subtract)\s+(?:of\s+)?{_NUM}\s+(?:and|,)\s+{_NUM}", re.I), "-"),
]

POWER_RE = re.compile(rf"{_NUM}\s*(?:to the power of|\*\*|\^)\s*{_NUM}", re.I)
FIB_RE = re.compile(r"fib(?:onacci)?(?:\s+of)?\s+(\d+)", re.I)

WORD_OPS = [
    (re.compile(r"\bto the power of\b|\*\*|\^", re.I), "**"),
    (re.compile(r"\bmultiplied by\b|\btimes\b", re.I), "*"),
    (re.compile(r"\bdivided by\b|\bover\b", re.I), "/"),
    (re.compile(r"\badded to\b|\bplus\b", re.I), "+"),
    (re.compile(r"\bsubtracted by\b|\bminus\b", re.I), "-"),
]

DEFAULT_OVERLAY: Dict[str, Any] = {
    "generation_id": 0,
    "compiler": {
        "chained_arithmetic": False,
        "power_operator": False,
        "extra_patterns": [],
    },
    "router_boosts": {},
    "retry": {
        "codeforge_wrap_print": True,
        "codeforge_eval_expr": False,
    },
    "intent_rules": [],
}

_local_overlay: Optional[Dict[str, Any]] = None


def default_overlay() -> Dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_OVERLAY))


def set_overlay(data: Optional[Dict[str, Any]]) -> None:
    global _local_overlay
    _local_overlay = data


def current_overlay() -> Dict[str, Any]:
    if _local_overlay is not None:
        return _local_overlay
    try:
        from evolution.overlay import get_active  # type: ignore
        active = get_active()
        if active is not None:
            return active.data
    except Exception:
        pass
    sibling = Path(__file__).resolve().parent / "overlay.json"
    if sibling.exists():
        try:
            return json.loads(sibling.read_text())
        except Exception:
            pass
    return default_overlay()


def _feature(name: str) -> bool:
    compiler = current_overlay().get("compiler") or {}
    return bool(compiler.get(name))


def compile_chained(msg: str) -> Optional[str]:
    text = (msg or "").lower()
    text = re.sub(r"[?!.,]+", " ", text)
    text = re.sub(r"^(what(?:'s| is)|calculate|compute|eval|please)\s+", "", text).strip()
    for rx, sym in WORD_OPS:
        text = rx.sub(f" {sym} ", text)
    text = re.sub(r"\s+", " ", text).strip()
    pattern = re.compile(
        r"(-?\d+(?:\.\d+)?)"
        r"(?:\s*(\*\*|[+\-*/])\s*(-?\d+(?:\.\d+)?))+"
    )
    m = pattern.search(text)
    if not m:
        return None
    expr = m.group(0).strip()
    ops = re.findall(r"\*\*|[+\-*/]", expr)
    if len(ops) < 1:
        return None
    if not _feature("chained_arithmetic") and len(ops) > 1:
        return None
    if "**" in ops and not _feature("power_operator"):
        return None
    if not re.fullmatch(r"[\d\s.+\-*/]+", expr.replace("**", "")):
        return None
    return f"print({expr})"


def compile_math(msg: str) -> Optional[str]:
    if _feature("chained_arithmetic") or _feature("power_operator"):
        chained = compile_chained(msg)
        if chained:
            return chained
    if _feature("power_operator"):
        m = POWER_RE.search(msg or "")
        if m:
            return f"print({m.group(1)} ** {m.group(2)})"
    for spec in (current_overlay().get("compiler") or {}).get("extra_patterns") or []:
        try:
            rx = re.compile(spec.get("pattern", ""), re.I)
            hit = rx.search(msg or "")
            if hit:
                op = spec.get("op", "+")
                return f"print({hit.group(1)} {op} {hit.group(2)})"
        except Exception:
            continue
    for rx, op in MATH_PATTERNS:
        m = rx.search(msg or "")
        if m:
            return f"print({m.group(1)} {op} {m.group(2)})"
    return None


def compile_fib(msg: str) -> Optional[str]:
    m = FIB_RE.search(msg or "")
    if not m:
        return None
    n = max(0, min(int(m.group(1)), 200))
    return (
        "def fib(n):\n"
        "    a, b = 0, 1\n"
        "    for _ in range(n):\n"
        "        a, b = b, a + b\n"
        "    return a\n"
        f"print(fib({n}))\n"
    )


def compile_any(msg: str) -> Optional[str]:
    return compile_math(msg) or compile_fib(msg)
