"""
Rapid Self-Improvement (RSI) for Vortex — upgraded to genuine evolution engine

Original closed loop that runs inside a turn, not overnight:
  observe → rescue → reflect → mutate → (optional) eval → promote

New evolution engine (OpenHands-inspired, Ultron-style):

                    SELF-IMPROVEMENT ENGINE

                    Observe
                       ↓
                 Find weakness
                       ↓
                Form hypothesis
                       ↓
              Generate candidate
                       ↓
                 Modify code
                       ↓
                  Sandbox
                       ↓
              Run regression tests
                       ↓
                Run benchmarks
                       ↓
               Security analysis
                       ↓
              Compare to baseline
                   ↙       ↘
                worse      better
                  ↓           ↓
                reject       stage
                              ↓
                          canary test
                              ↓
                           deploy
                              ↓
                           monitor
                              ↓
                          rollback

Do not let Vortex directly overwrite production code.
Use versioned candidates:
  vortex/releases/v001/, v002/, v003/

Every improvement gets:
  generation_id
  parent_generation
  change_set
  benchmark_results
  security_results
  performance_results
  decision
"""
from __future__ import annotations

import json
import re
import time
import shutil
import tempfile
import subprocess
import sys
import os
from collections import Counter
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime

from tools import TOOL_CLASSES, ToolResult
from tools.base import ToolResult as BaseToolResult

from evolution.compiler import (
    MATH_PATTERNS,
    FIB_RE,
    compile_math as _overlay_compile_math,
    compile_fib as _overlay_compile_fib,
)
from evolution.engine import (
    EvolutionEngine,
    WeaknessFinder,
    HypothesisGenerator,
    BenchmarkRunner,
)
from evolution.patcher import CandidateGenerator, CandidatePatcher
from evolution.sandbox import SandboxRunner
from evolution.security import SecurityScanner

STOP = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "it",
    "me", "my", "please", "can", "you", "we", "i", "this", "that", "with",
    "from", "at", "be", "as", "do", "what", "how", "whats",
}
HIDE_RE = re.compile(r"\b(hide|encode|conceal|secret)\b", re.I)
REVEAL_RE = re.compile(r"\b(reveal|decode|extract|unhide)\b", re.I)
TRANSLATE_RE = re.compile(r"\b(translate|conlang|obfuscate|gloss)\b", re.I)
CODE_HINT = re.compile(r"\b(run|execute|eval|python|script|benchmark)\b", re.I)

WEAK_MARKERS = (
    "don't have a live llm",
    "i don't have a live",
    "standing by",
    "plan drafted",
    "ack:",
    "give me a task",
    "try /help",
    "core brain is online",
)


def tokenize(text: str):
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in STOP and len(t) > 1]


def compile_math(msg: str) -> Optional[str]:
    """Delegate to the active evolution overlay (baseline = original two-operand math)."""
    return _overlay_compile_math(msg)


def compile_fib(msg: str) -> Optional[str]:
    return _overlay_compile_fib(msg)


def is_weak(reply: str) -> bool:
    low = (reply or "").lower()
    return any(m in low for m in WEAK_MARKERS)


class LearnedRouter:
    """Token → target weights that compound across successful turns."""

    def __init__(self, memory):
        self.memory = memory
        raw = memory.get_kv("rsi_router")
        self.weights = json.loads(raw) if raw else {}

    def persist(self):
        self.memory.set_kv("rsi_router", json.dumps(self.weights))

    def snapshot(self):
        return json.dumps(self.weights)

    def restore(self, snap: str):
        self.weights = json.loads(snap) if snap else {}
        self.persist()

    def observe(self, message: str, target: str, success: bool):
        if not target:
            return
        delta = 1.0 if success else -0.25
        for tok in tokenize(message):
            bucket = self.weights.setdefault(tok, {})
            bucket[target] = round(bucket.get(target, 0.0) + delta, 3)
        self.persist()

    def suggest(self, message: str, min_score: float = 1.4):
        scores = Counter()
        for tok in tokenize(message):
            for target, w in self.weights.get(tok, {}).items():
                if w > 0:
                    scores[target] += w
        try:
            from evolution.overlay import get_active
            boosts = (get_active().data or {}).get("router_boosts") or {}
            for tok in tokenize(message):
                bucket = boosts.get(tok) or {}
                if not isinstance(bucket, dict):
                    continue
                for target, w in bucket.items():
                    if w:
                        scores[target] += float(w)
        except Exception:
            pass
        if not scores:
            return None
        target, score = scores.most_common(1)[0]
        if score >= min_score:
            return target, score
        return None


class IntentCompiler:
    """Turn a natural-language miss into a concrete tool call."""

    @staticmethod
    def compile(message: str):
        code = compile_math(message) or compile_fib(message)
        if code:
            return {
                "kind": "intent",
                "trigger": "math" if compile_math(message) else "fibonacci",
                "action": "tool:codeforge",
                "tool": "codeforge",
                "args": {"code": code},
                "confidence": 0.9,
            }

        low = message.lower()
        if TRANSLATE_RE.search(message) or "into vortex" in low:
            text = TRANSLATE_RE.sub("", message)
            text = re.sub(r"^(please\s+)?", "", text, flags=re.I).strip(" :")
            return {
                "kind": "intent",
                "trigger": "translate",
                "action": "tool:glossopetrae",
                "tool": "glossopetrae",
                "args": {"text": text or message},
                "confidence": 0.85,
            }

        if REVEAL_RE.search(message):
            return {
                "kind": "intent",
                "trigger": "reveal",
                "action": "tool:steganography:decode",
                "tool": "steganography",
                "args": {"action": "decode", "stego": message},
                "confidence": 0.8,
            }

        if HIDE_RE.search(message):
            rest = HIDE_RE.sub("", message, count=1).strip(" :")
            if "|" in rest:
                payload, _, cover = rest.partition("|")
            elif " in " in rest.lower():
                idx = rest.lower().find(" in ")
                payload, cover = rest[:idx], rest[idx + 4:]
            else:
                payload, cover = rest, ""
            return {
                "kind": "intent",
                "trigger": "hide",
                "action": "tool:steganography:encode",
                "tool": "steganography",
                "args": {
                    "action": "encode",
                    "payload": payload.strip() or message,
                    "cover": cover.strip(),
                },
                "confidence": 0.8,
            }

        if CODE_HINT.search(message) and "```" in message:
            m = re.search(r"```(?:python)?\s*(.*?)```", message, re.S)
            if m:
                return {
                    "kind": "intent",
                    "trigger": "run-code",
                    "action": "tool:codeforge",
                    "tool": "codeforge",
                    "args": {"code": m.group(1).strip()},
                    "confidence": 0.88,
                }
        return None


class Reflector:
    """Turn a trace into zero or more reusable lessons."""

    def extract(self, task: str, reply: str, tool: Optional[str],
                status: Optional[str], score: float):
        lessons = []
        intent = IntentCompiler.compile(task)
        if intent and (not tool or status != "success" or score < 0.7):
            lessons.append({
                "kind": "routing",
                "trigger": intent["trigger"],
                "action": intent["action"],
                "confidence": intent["confidence"],
                "meta": {"example": task[:160]},
            })
        if tool and status == "success":
            for tok in tokenize(task)[:8]:
                lessons.append({
                    "kind": "routing",
                    "trigger": tok,
                    "action": f"tool:{tool}",
                    "confidence": 0.7,
                    "meta": {"source": "success-trace"},
                })
        if is_weak(reply) and intent:
            lessons.append({
                "kind": "rescue",
                "trigger": intent["trigger"],
                "action": intent["action"],
                "confidence": 0.86,
                "meta": {"note": "weak reply rescued by compiler"},
            })
        return lessons


# Evolution engine lives in backend/evolution/ (real patches, sandbox, canary, rollback).
# WeaknessFinder, HypothesisGenerator, CandidateGenerator, SandboxRunner,
# BenchmarkRunner, SecurityScanner, EvolutionEngine are imported from that package.

class RapidSelfImprovement:
    """Owns the online loop and the slower eval/promote cycle — now with EvolutionEngine."""

    def __init__(self, agent):
        self.agent = agent
        self.memory = agent.memory
        self.router = LearnedRouter(agent.memory)
        self.reflector = Reflector()
        self.tools = {t.name: t for t in TOOL_CLASSES}
        self.eval_mode = False
        self.last_cycle = None
        # evolution engine
        try:
            from governance import Governance
            gov = Governance(memory=self.memory)
        except:
            gov = None
        self.evolution = EvolutionEngine(agent=self.agent, memory=self.memory, governance=gov)
        if self.memory.current_generation() == 0:
            self.memory.save_generation(
                None, 0.0, [], "genesis — RSI online, no eval yet")

    # ── routing overlay ──
    def suggest_route(self, message: str, role: str = ""):
        hit = self.router.suggest(message)
        if not hit:
            intent = IntentCompiler.compile(message)
            if intent:
                return intent["tool"], intent["args"], intent
            return None
        target, _score = hit
        # target like "tool:codeforge" or "bot:architect"
        if target.startswith("tool:"):
            tool = target.split(":")[1]
            args = self._args_for(tool, message)
            if args is None:
                return None
            return tool, args, {"kind": "learned", "action": target, "trigger": "router"}
        return None

    def _args_for(self, tool: str, message: str):
        intent = IntentCompiler.compile(message)
        if intent and intent["tool"] == tool:
            return intent["args"]
        if tool == "codeforge":
            code = compile_math(message) or compile_fib(message)
            if code:
                return {"code": code}
            return None
        if tool == "glossopetrae":
            text = TRANSLATE_RE.sub("", message).strip(" :") or message
            return {"text": text}
        if tool == "steganography":
            if REVEAL_RE.search(message):
                return {
                    "action": "decode",
                    "stego": self.memory.get_kv("last_stego") or message,
                }
            return {"action": "encode", "payload": message, "cover": ""}
        return None

    # ── same-turn rescue ──
    def rescue(self, message: str, reply: str, bot: str):
        if not is_weak(reply):
            return None
        intent = IntentCompiler.compile(message)
        if not intent:
            return None
        tool = self.tools.get(intent["tool"])
        if not tool:
            return None
        args = intent["args"]
        if intent["tool"] == "steganography" and args.get("action") == "decode":
            args = {**args, "stego": args.get("stego") or self.memory.get_kv("last_stego") or ""}
        try:
            result = tool.execute(**args)
        except Exception as e:
            result = ToolResult("error", {}, f"rescue crashed: {e}")
        if result.status != "success":
            return None
        lesson_id = self.memory.save_lesson({
            "kind": "rescue",
            "trigger": intent["trigger"],
            "action": intent["action"],
            "confidence": 0.9,
            "meta": {"bot": bot, "example": message[:160]},
        })
        self.router.observe(message, f"tool:{intent['tool']}", True)
        return {
            "tool": intent["tool"],
            "args": args,
            "result": result,
            "lesson_id": lesson_id,
            "intent": intent,
        }

    def retry_tool(self, tool_name: str, args: dict, error_msg: str):
        """Mutate args from a known failure and retry once."""
        bug = self.agent.bugs.match(error_msg or "")
        mutated = dict(args)
        if tool_name == "codeforge":
            code = mutated.get("code") or ""
            if "syntax" in (error_msg or "").lower() and "print" not in code:
                mutated["code"] = f"print({code.strip()})"
            elif bug and bug.get("fix_code"):
                mutated["code"] = bug["fix_code"]
            else:
                return None
        elif tool_name == "steganography" and args.get("action") == "decode":
            last = self.memory.get_kv("last_stego")
            if last and last != args.get("stego"):
                mutated["stego"] = last
            else:
                return None
        else:
            return None
        tool = self.tools.get(tool_name)
        if not tool:
            return None
        try:
            result = tool.execute(**mutated)
        except Exception as e:
            return None
        if result.status == "success":
            self.memory.save_lesson({
                "kind": "bugfix",
                "trigger": (error_msg or "")[:80],
                "action": f"retry:{tool_name}",
                "confidence": 0.8,
                "meta": {"from": args, "to": mutated},
            })
            return result, mutated
        return None

    # ── observe / score ──
    def score(self, reply: str, tool: Optional[str], status: Optional[str],
              rescued: bool = False) -> float:
        if status == "success":
            base = 1.0 if not rescued else 0.92
        elif status == "error":
            base = 0.15
        elif is_weak(reply):
            base = 0.28
        elif reply.startswith("🧩"):
            base = 0.8
        else:
            base = 0.55
        return round(base, 3)

    def observe(self, task: str, reply: str, bot: str = "chief",
                tool: Optional[str] = None, status: Optional[str] = None,
                route: Optional[str] = None, latency_ms: int = 0,
                rescued: bool = False, extra: Optional[dict] = None):
        if self.eval_mode:
            return None
        sc = self.score(reply, tool, status, rescued=rescued)
        tid = self.memory.save_trace({
            "generation": self.memory.current_generation(),
            "task": task,
            "bot": bot,
            "route": route,
            "tool": tool,
            "status": status or ("rescued" if rescued else "reply"),
            "score": sc,
            "latency_ms": latency_ms,
            "detail": {
                "rescued": rescued,
                "reply_preview": (reply or "")[:240],
                **(extra or {}),
            },
        })
        if tool and status == "success":
            self.router.observe(task, f"tool:{tool}", True)
        elif status == "error":
            self.router.observe(task, f"tool:{tool}", False)
        for lesson in self.reflector.extract(task, reply, tool, status, sc):
            self.memory.save_lesson(lesson)
        if sc >= 0.8:
            self.agent.vector.remember(
                f"[rsi/win gen={self.memory.current_generation()}] {task} -> {reply[:160]}")
            # also push to enhanced memory if available
            try:
                if hasattr(self.memory, 'remember'):
                    self.memory.remember(f"{task} -> {reply[:160]}", kind="episodic", meta={"bot": bot, "score": sc})
            except:
                pass
        return tid

    # ── eval / promote ──
    def status(self) -> dict:
        gens = self.memory.get_generations(5)
        evals = self.memory.get_evals(5)
        lessons = self.memory.get_lessons(True)
        traces = self.memory.get_traces(8)
        avg = 0.0
        recent = self.memory.get_traces(20)
        if recent:
            avg = round(sum(t["score"] or 0 for t in recent) / len(recent), 3)
        return {
            "generation": self.memory.current_generation(),
            "active_lessons": len(lessons),
            "router_tokens": len(self.router.weights),
            "recent_avg_score": avg,
            "last_cycle": self.last_cycle,
            "latest_eval": evals[0] if evals else None,
            "generations": gens,
            "lessons": lessons[:20],
            "traces": traces,
            "eval_mode": self.eval_mode,
            "evolution": self.evolution.status() if hasattr(self, 'evolution') else {},
        }

    def run_cycle(self, persist=True) -> dict:
        """Reflect on recent traces, apply pending high-signal lessons, eval, promote or roll back — now with full evolution engine."""
        from evals import run_suite

        snap = self.router.snapshot()
        before_lessons = {l["id"] for l in self.memory.get_lessons(True)}

        # harvest any leftover intent from recent weak traces
        applied = []
        for tr in self.memory.get_traces(30):
            for lesson in self.reflector.extract(
                tr["task"], (tr.get("detail") or {}).get("reply_preview", ""),
                tr.get("tool"), tr.get("status"), tr.get("score") or 0,
            ):
                lid = self.memory.save_lesson(lesson)
                applied.append({"lesson_id": lid, **lesson})

        before = run_suite(self.agent, persist=False)
        after = before
        after = run_suite(self.agent, persist=persist, name="cycle-after")

        # use evolution engine for deeper improvement decision if available
        evolution_record = None
        try:
            evolution_record = self.evolution.evolve_once(eval_result=after)
        except Exception as e:
            evolution_record = {"decision": "evolution_error", "error": str(e)[:200]}

        improved = after["score"] >= before["score"] - 0.001
        notes = (
            f"cycle: {before['score']:.3f} → {after['score']:.3f} "
            f"({after['passed']}/{after['total']} passed)"
        )
        if evolution_record and evolution_record.get("decision") in ("promoted", "rejected", "canary_failed"):
            notes += f" | evolution: {evolution_record.get('decision')} ({evolution_record.get('reason','')})"

        if improved:
            gen = self.memory.save_generation(
                self.memory.current_generation(),
                after["score"],
                applied[:12],
                notes,
            )
            decision = "promoted"
        else:
            self.router.restore(snap)
            new_ids = [l["id"] for l in self.memory.get_lessons(True)
                       if l["id"] not in before_lessons]
            self.memory.set_lessons_active(new_ids, False)
            gen = self.memory.current_generation()
            decision = "reverted"
            notes += " — reverted (no gain)"

        self.last_cycle = {
            "decision": decision,
            "generation": gen,
            "before": before,
            "after": after,
            "applied": len(applied),
            "notes": notes,
            "evolution": evolution_record,
        }
        self.memory.log_event("rsi_cycle", notes)
        return self.last_cycle

    def report(self) -> str:
        s = self.status()
        lines = [
            f"🧬 RSI generation {s['generation']}",
            f"   active lessons : {s['active_lessons']}",
            f"   router tokens  : {s['router_tokens']}",
            f"   recent avg     : {s['recent_avg_score']}",
        ]
        if s["latest_eval"]:
            e = s["latest_eval"]
            lines.append(
                f"   last eval      : {e['score']:.3f}  ({e['passed']}/{e['total']})  gen {e['generation']}"
            )
        if s["last_cycle"]:
            lines.append(f"   last cycle     : {s['last_cycle']['notes']}")
            evo = s['last_cycle'].get('evolution')
            if evo:
                lines.append(f"   evolution      : {evo.get('decision')} — {evo.get('reason','')[:80]}")
        if s.get("evolution"):
            evo = s["evolution"]
            lines.append(f"   releases       : {evo.get('releases',0)}  last={evo.get('last_candidate',{}).get('decision','-') if evo.get('last_candidate') else '-'}")
        if s["lessons"]:
            lines.append("   top lessons:")
            for l in s["lessons"][:6]:
                lines.append(
                    f"     • [{l['kind']}] {l['trigger']} → {l['action']}  "
                    f"(c={l['confidence']:.2f}, {l['wins']}w/{l['losses']}l)"
                )
        return "\n".join(lines)
