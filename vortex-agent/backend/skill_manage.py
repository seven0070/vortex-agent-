"""
Vortex autonomous skill creation (Hermes `skill_manage` equivalent).

Before this, `skills.save()` had exactly one caller in the whole codebase, writing one
hardcoded skill named "multi_bot_analysis". The library existed; nothing filled it.

Hermes' rule: after a non-trivial task (5+ tool calls, or a tricky fix), write the
approach down as a reusable skill; if a skill already exists but performed badly,
improve it. This implements that loop over Vortex's existing SkillLibrary +
ProceduralMemory, so skills become real procedural memory instead of a stub.

Deterministic by default — the trigger, naming and step capture need no LLM. When a
model is configured it writes a better description, but the skill is still created
without one.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

# Hermes uses "5+ tool calls" as its complexity bar, but that threshold does not
# transfer: Vortex's RSI compiler deliberately collapses whole requests into ONE tool
# call, and multi-bot work shows up as delegations rather than calls. Measured on real
# turns, a 5-call bar never fires and even 3 misses ordinary two-specialist plans.
# So: 2+ tool calls, or 2+ delegated steps, or any rescue/retry.
COMPLEXITY_TOOL_CALLS = 2      # per-turn tool calls that make a turn "complex"
COMPLEXITY_STEPS = 2           # or this many delegated steps
STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "that", "this", "from", "into",
    "please", "can", "you", "how", "what", "why", "when", "make", "give", "show",
    "then", "some", "about", "would", "could", "should", "there", "their", "have",
}


def slugify(text: str, max_words: int = 4) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
             if w not in STOPWORDS and len(w) > 2]
    return "_".join(words[:max_words]) or "task"


class SkillManager:
    """Creates and improves skills from experience."""

    def __init__(self, agent):
        self.agent = agent
        self.created = 0
        self.improved = 0
        self.considered = 0

    # ── trigger ──
    @staticmethod
    def is_complex(tool_calls: int = 0, steps: int = 0, rescued: bool = False,
                   retried: bool = False) -> bool:
        """
        Was this turn worth remembering how to do?

        A rescue or a retry counts even when short: those are exactly the
        "tricky fix" cases where the lesson is most valuable next time.
        """
        return (tool_calls >= COMPLEXITY_TOOL_CALLS
                or steps >= COMPLEXITY_STEPS
                or rescued or retried)

    # ── create / improve ──
    def capture(self, goal: str, steps: List[Any], outcome: str = "",
                success: bool = True, meta: Optional[dict] = None) -> Optional[Dict[str, Any]]:
        """
        Write this approach down, or improve the existing skill for it.
        Returns the skill dict, or None if nothing was worth saving.
        """
        self.considered += 1
        if not goal or not steps:
            return None

        name = slugify(goal)
        existing = None
        try:
            existing = self.agent.skills.get(name)
        except Exception:
            pass

        steps_clean = [str(s)[:200] for s in steps if s][:12]
        if not steps_clean:
            return None

        description = self._describe(goal, steps_clean, success)

        if existing:
            # improve in place: merge steps, track outcomes
            prior = existing.get("steps") or []
            merged, seen = [], set()
            for s in list(prior) + steps_clean:
                k = str(s)[:120]
                if k not in seen:
                    seen.add(k)
                    merged.append(s)
            uses = int(existing.get("uses", 1)) + 1
            wins = int(existing.get("wins", 0)) + (1 if success else 0)
            payload = {
                "name": name,
                "description": description or existing.get("description", ""),
                "steps": merged[:16],
                "uses": uses,
                "wins": wins,
                "success_rate": round(wins / uses, 3) if uses else 0.0,
                "updated": datetime.now().isoformat(),
                "goal_example": goal[:200],
            }
            self._persist(payload, improved=True)
            self.improved += 1
            return payload

        payload = {
            "name": name,
            "description": description,
            "steps": steps_clean,
            "uses": 1,
            "wins": 1 if success else 0,
            "success_rate": 1.0 if success else 0.0,
            "created": datetime.now().isoformat(),
            "goal_example": goal[:200],
        }
        self._persist(payload, improved=False)
        self.created += 1
        return payload

    def _persist(self, payload: Dict[str, Any], improved: bool) -> None:
        # SkillLibrary.save has a fixed signature; write the rich record directly
        # so uses/wins survive, then fall back to the simple API if that fails.
        try:
            import json
            path = self.agent.skills.dir / f"{payload['name']}.json"
            base = {}
            if path.exists():
                try:
                    base = json.loads(path.read_text())
                except Exception:
                    base = {}
            base.update(payload)
            base.setdefault("shared", True)
            path.write_text(json.dumps(base, indent=2))
        except Exception:
            try:
                self.agent.skills.save(payload["name"], payload["description"], payload["steps"])
            except Exception:
                return

        # mirror into procedural memory (layer 4) so /memory recall sees it
        try:
            mem = getattr(self.agent, "memory", None)
            if mem is not None and hasattr(mem, "procedural"):
                mem.procedural.save_procedure(
                    name=payload["name"],
                    description=payload["description"],
                    steps=payload["steps"],
                    meta={"auto": True, "improved": improved},
                )
        except Exception:
            pass

        try:
            if getattr(self.agent, "memory", None) and hasattr(self.agent.memory, "episodic"):
                verb = "improved" if improved else "created"
                self.agent.memory.episodic.remember_event(
                    f"Skill {verb}: {payload['name']} — {payload['description'][:80]}",
                    kind="skill",
                    meta={"skill": payload["name"], "improved": improved},
                )
        except Exception:
            pass

    def _describe(self, goal: str, steps: List[str], success: bool) -> str:
        """LLM writes a better description when available; deterministic otherwise."""
        try:
            from llm import get_llm
            llm = get_llm()
            if llm.available:
                r = llm.complete(
                    "You write one-sentence descriptions of reusable agent procedures. "
                    "Under 20 words, imperative mood, no preamble.",
                    f"Goal: {goal}\nSteps taken:\n" + "\n".join(f"- {s[:120]}" for s in steps[:6]),
                    temperature=0.2, max_tokens=60,
                )
                if r and len(r.text) < 200:
                    return r.text.strip().strip('"')
        except Exception:
            pass
        outcome = "succeeded" if success else "failed"
        return f"Procedure for '{goal[:60]}' ({len(steps)} steps, last run {outcome})."

    # ── retrieval ──
    def find(self, goal: str) -> Optional[Dict[str, Any]]:
        """Look for an existing skill relevant to this goal (checked before acting)."""
        if not goal:
            return None
        try:
            skills = self.agent.skills.list()
        except Exception:
            return None
        if not skills:
            return None
        want = set(w for w in re.findall(r"[a-z0-9]+", goal.lower())
                   if w not in STOPWORDS and len(w) > 2)
        if not want:
            return None
        best, best_score = None, 0.0
        for s in skills:
            hay = set(re.findall(r"[a-z0-9]+", f"{s.get('name','')} {s.get('goal_example','')}".lower()))
            if not hay:
                continue
            overlap = len(want & hay) / max(1, len(want))
            if overlap > best_score:
                best, best_score = s, overlap
        return best if best_score >= 0.5 else None

    def stats(self) -> Dict[str, Any]:
        try:
            skills = self.agent.skills.list()
        except Exception:
            skills = []
        auto = [s for s in skills if "uses" in s]
        return {
            "total_skills": len(skills),
            "auto_created": self.created,
            "auto_improved": self.improved,
            "turns_considered": self.considered,
            "tracked": [
                {"name": s.get("name"), "uses": s.get("uses"),
                 "success_rate": s.get("success_rate")}
                for s in sorted(auto, key=lambda x: -int(x.get("uses", 0)))[:10]
            ],
        }
