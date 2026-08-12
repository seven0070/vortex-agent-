"""Built-in eval suite used by Rapid Self-Improvement.

Each case is a user message plus a judge. Judges are pure functions so
the loop cannot reward-hack a live model — a reply either contains the
expected signal or it does not.
"""
from __future__ import annotations


def _contains(*needles):
    def judge(reply: str) -> bool:
        low = (reply or "").lower()
        return all(n.lower() in low for n in needles)
    return judge


def _not_weak_and(*needles):
    weak = ("don't have a live", "try /help", "standing by", "plan drafted")

    def judge(reply: str) -> bool:
        low = (reply or "").lower()
        if any(w in low for w in weak):
            return False
        return all(n.lower() in low for n in needles)
    return judge


CASES = [
    {
        "name": "nl-math-multiply",
        "message": "what is 12 times 8",
        "judge": _contains("96"),
        "weight": 1.2,
    },
    {
        "name": "nl-math-sum",
        "message": "sum of 40 and 2",
        "judge": _contains("42"),
        "weight": 1.0,
    },
    {
        "name": "slash-run",
        "message": "/run print(3+4)",
        "judge": _contains("7"),
        "weight": 1.0,
    },
    {
        "name": "translate",
        "message": "/translate the warrior sees the mountain",
        "judge": _contains("glossopetrae"),
        "weight": 0.8,
    },
    {
        "name": "hide-payload",
        "message": "/hide secret-token | cover story",
        "judge": _contains("stego", "secret-token"),
        "weight": 0.8,
    },
    {
        "name": "fibonacci-nl",
        "message": "fibonacci of 10",
        "judge": _contains("55"),
        "weight": 1.1,
    },
    {
        "name": "help",
        "message": "who are you",
        "judge": lambda r: "vortex" in (r or "").lower() or "chief" in (r or "").lower(),
        "weight": 0.4,
    },
]


def run_suite(agent, persist=True, name="suite") -> dict:
    """Run canned tasks against the live swarm. Learning is frozen."""
    rsi = agent.rsi
    prev = rsi.eval_mode
    rsi.eval_mode = True
    results = []
    passed = 0
    total_w = 0.0
    earned = 0.0
    try:
        for case in CASES:
            try:
                reply = agent.chat(case["message"])
            except Exception as e:
                reply = f"EVAL ERROR: {e}"
            ok = bool(case["judge"](reply))
            w = float(case.get("weight", 1.0))
            total_w += w
            if ok:
                passed += 1
                earned += w
            results.append({
                "name": case["name"],
                "ok": ok,
                "weight": w,
                "reply": (reply or "")[:220],
            })
    finally:
        rsi.eval_mode = prev

    score = round(earned / total_w, 4) if total_w else 0.0
    payload = {
        "name": name,
        "passed": passed,
        "total": len(CASES),
        "score": score,
        "cases": results,
    }
    if persist:
        agent.memory.save_eval(
            agent.memory.current_generation(),
            name, passed, len(CASES), score,
            {"cases": results},
        )
    return payload


def format_suite(result: dict) -> str:
    lines = [
        f"🧪 eval '{result['name']}': {result['passed']}/{result['total']}  "
        f"score={result['score']:.3f}",
    ]
    for c in result["cases"]:
        mark = "✅" if c["ok"] else "❌"
        lines.append(f"   {mark} {c['name']}")
    return "\n".join(lines)
