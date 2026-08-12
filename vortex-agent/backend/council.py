"""
Vortex Council — real multi-agent deliberation (Microsoft Agent Framework patterns)

Architecture:
                    VORTEX COUNCIL
Researcher ───────┐
Planner ──────────┤
Engineer ─────────┤
Critic ───────────┼──→ Deliberation
Security ─────────┤
Strategist ───────┤
Verifier ─────────┘
                         ↓
                     Resolution

Protocol:
proposal → independent analyses → critic phase → evidence comparison → confidence scoring → vote / weighted decision → resolution

Roles:
- Researcher: recall memory, gather context
- Planner: decompose, sequencing
- Engineer: build / code / tool execution
- Critic: challenge assumptions, find flaws
- Security: policy, risk, safety, steganography
- Strategist: objectives alignment, cost/latency tradeoff
- Verifier: correctness, test, evidence

Based on MS Agent Framework: sequential, concurrent, handoff, group-collaboration patterns.
"""
from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

ROLE_PROMPTS = {
    "Researcher": "You gather facts, recall memory, and provide evidence. Be concise but cite sources.",
    "Planner": "You decompose goals into steps, sequence tasks, and identify dependencies.",
    "Engineer": "You implement, build, run code, and produce tangible artifacts. Prefer tool calls.",
    "Critic": "You challenge proposals, find failure modes, ask hard questions. Be constructive but skeptical.",
    "Security": "You assess policy compliance, risk, safety, and enforce governance. Check for leaks.",
    "Strategist": "You align with Vortex objectives, consider cost/latency/risk, and prioritize.",
    "Verifier": "You verify correctness, run checks, compare evidence, and score confidence.",
}

# weights for voting — can be tuned by self-improvement
DEFAULT_WEIGHTS = {
    "Researcher": 1.0,
    "Planner": 1.1,
    "Engineer": 1.2,
    "Critic": 1.3,
    "Security": 1.2,
    "Strategist": 1.1,
    "Verifier": 1.4,
}

@dataclass
class CouncilMember:
    role: str
    weight: float
    bot_name: str  # underlying bot that implements role
    analyses: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.analyses is None:
            self.analyses = []

class VortexCouncil:
    def __init__(self, agent=None, memory=None, governance=None, weights: Dict[str, float] = None):
        self.agent = agent
        self.memory = memory
        self.governance = governance
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        self.members: Dict[str, CouncilMember] = {}
        self._init_members()

    def _init_members(self):
        # map council roles to underlying swarm bots
        bot_map = {
            "Researcher": "researcher",
            "Planner": "chief",
            "Engineer": "architect",
            "Critic": "researcher",  # reuse researcher as critic but distinct prompt
            "Security": "cipher",
            "Strategist": "chief",
            "Verifier": "architect",
        }
        for role, bot_name in bot_map.items():
            self.members[role] = CouncilMember(role=role, weight=self.weights.get(role, 1.0), bot_name=bot_name)

    def deliberate(self, state=None, goal: str = None, candidates: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Full Council protocol.

        Input: state (VortexState) or goal + candidates
        Output: deliberation dict with independent analyses, critic notes, evidence comparison, vote, final
        """
        from orchestration.state import VortexState

        if isinstance(state, VortexState):
            goal = state.goal
            candidates = [t.result for t in state.tasks if t.result] if hasattr(state, 'tasks') else candidates
        goal = goal or (state.goal if state else "general task")
        candidates = candidates or []

        # Phase 1: proposal
        proposal = self._form_proposal(goal, candidates)

        # Phase 2: independent analyses (concurrent pattern)
        analyses = {}
        for role, member in self.members.items():
            analysis = self._independent_analysis(role, goal, proposal, candidates)
            analyses[role] = analysis

        # Phase 3: critic phase
        critic_notes = self._critic_phase(analyses, proposal, goal)

        # Phase 4: evidence comparison
        evidence_matrix = self._compare_evidence(analyses)

        # Phase 5: confidence scoring
        confidence_scores = self._score_confidence(analyses, critic_notes, evidence_matrix)

        # Phase 6: vote / weighted decision
        vote = self._vote(analyses, confidence_scores)

        # Phase 7: synthesis of views only — Council does not pick an executable winner.
        # VortexResolver is the authority that selects; Governance authorizes execution.
        final = self._synthesize_final(goal, proposal, analyses, critic_notes, vote, evidence_matrix)

        deliberation = {
            "goal": goal,
            "executes": False,
            "role": "generate_views",
            "proposal": proposal,
            "analyses": analyses,
            "critic_notes": critic_notes,
            "evidence_comparison": evidence_matrix,
            "confidence_scores": confidence_scores,
            "vote": vote,
            "final": final,
            "decision": vote.get("winner", "no_consensus"),
            "confidence": vote.get("confidence", 0.6),
            "timestamp": datetime.now().isoformat(),
        }

        # save to episodic memory
        if self.memory:
            try:
                self.memory.episodic.remember_event(
                    f"Council deliberation on '{goal[:60]}' → {vote.get('winner')} conf={vote.get('confidence'):.2f}",
                    kind="council",
                    meta={"goal": goal, "decision": vote.get("winner"), "confidence": vote.get("confidence")}
                )
                # cross-agent sharing
                self.memory.agent_memory.remember("council", final[:300], kind="deliberation")
            except:
                pass

        return deliberation

    def _form_proposal(self, goal: str, candidates: List[Any]) -> str:
        if candidates:
            return f"Goal: {goal}\nCandidates: {str(candidates)[:500]}"
        return f"Goal: {goal}\nNo candidates yet, propose solution."

    def _independent_analysis(self, role: str, goal: str, proposal: str, candidates: List[Any]) -> Dict[str, Any]:
        """
        Each role does independent analysis.
        If agent present, delegate to bot; otherwise heuristic.
        """
        # Advise-only: council generates competing views and must not execute tools.
        analysis_text = self._heuristic_role_analysis(role, goal, candidates)
        evidence = [f"{role} evidence for {goal[:80]}"]
        confidence = 0.62
        if self.memory:
            try:
                hits = self.memory.recall(goal, n=2) or []
                if hits:
                    evidence.append(str(hits[0])[:200])
                    confidence = 0.72
            except Exception:
                pass

        return {
            "role": role,
            "analysis": analysis_text,
            "evidence": evidence,
            "confidence": confidence,
            "weight": self.members[role].weight,
        }

    def _heuristic_role_analysis(self, role: str, goal: str, candidates: List[Any]) -> str:
        low = goal.lower()
        if role == "Researcher":
            # recall memory if available
            mem_hits = []
            if self.memory:
                try:
                    mem_hits = self.memory.recall(goal, n=2)
                except:
                    pass
            return f"Researcher: recalled {len(mem_hits)} memories. Goal '{goal[:80]}' requires {'research' if 'research' in low else 'general'} approach. Evidence: {str(mem_hits)[:200]}"
        if role == "Planner":
            steps = ["understand", "decompose", "route", "execute", "observe", "resolve"]
            return f"Planner: plan steps = {steps} for goal '{goal[:80]}'"
        if role == "Engineer":
            tool = "codeforge" if any(k in low for k in ("code", "fibonacci", "calculate", "run")) else "general"
            return f"Engineer: implementation via {tool} for '{goal[:80]}'"
        if role == "Critic":
            return f"Critic: risks for '{goal[:80]}' → check for weak replies, missing tool calls, unverified outputs"
        if role == "Security":
            risk = "medium" if any(k in low for k in ("code", "execute")) else "low"
            return f"Security: risk={risk}, policy check needed for '{goal[:80]}'"
        if role == "Strategist":
            return f"Strategist: align with objectives, prioritize quick win for '{goal[:80]}'"
        if role == "Verifier":
            return f"Verifier: verify {'candidates ' + str(len(candidates)) if candidates else 'no candidates'} for '{goal[:80]}'"
        return f"{role}: analysis for '{goal[:80]}'"

    def _critic_phase(self, analyses: Dict[str, Dict[str, Any]], proposal: str, goal: str) -> List[Dict[str, Any]]:
        notes = []
        # critic role challenges each analysis
        critic = analyses.get("Critic", {})
        critic_text = critic.get("analysis", "")

        for role, analysis in analyses.items():
            if role == "Critic":
                continue
            # simple heuristic critique
            challenge = ""
            if analysis["confidence"] < 0.5:
                challenge = f"Low confidence from {role} ({analysis['confidence']:.2f}) → needs verification"
            elif len(analysis["analysis"]) < 30:
                challenge = f"{role} analysis too brief → request evidence"
            else:
                challenge = f"{role} analysis reviewed, no major flaw"

            notes.append({
                "target": role,
                "critic_note": challenge,
                "severity": "high" if "low confidence" in challenge.lower() else "low"
            })

        # overall critic synthesis
        notes.append({
            "target": "proposal",
            "critic_note": critic_text[:300] or "Critic: check overall consistency",
            "severity": "medium"
        })
        return notes

    def _compare_evidence(self, analyses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        # Build evidence comparison matrix
        all_evidence = []
        for role, data in analyses.items():
            for ev in data.get("evidence", []):
                all_evidence.append({"role": role, "evidence": ev, "confidence": data.get("confidence", 0.5)})

        # group by similarity (simple)
        groups = {}
        for ev in all_evidence:
            key = ev["evidence"][:30].lower()
            if key not in groups:
                groups[key] = []
            groups[key].append(ev)

        consensus = [g for g in groups.values() if len(g) >= 2]
        conflicts = [g for g in groups.values() if len(g) == 1]

        return {
            "total_evidence": len(all_evidence),
            "consensus_groups": len(consensus),
            "conflict_groups": len(conflicts),
            "groups": list(groups.values())[:5],  # sample
        }

    def _score_confidence(self, analyses: Dict[str, Dict[str, Any]], critic_notes: List[Dict], evidence_matrix: Dict) -> Dict[str, float]:
        scores = {}
        for role, data in analyses.items():
            base = data.get("confidence", 0.5)
            weight = data.get("weight", 1.0)
            # penalize if criticized high severity
            penalties = sum(0.15 for n in critic_notes if n["target"] == role and n["severity"] == "high")
            bonuses = 0.05 * evidence_matrix.get("consensus_groups", 0)
            final = max(0.05, min(0.99, base * (0.8 + weight*0.2) - penalties + bonuses))
            scores[role] = round(final, 3)
        return scores

    def _vote(self, analyses: Dict[str, Dict[str, Any]], confidence_scores: Dict[str, float]) -> Dict[str, Any]:
        # weighted vote: each role votes for its own analysis unless low confidence
        # if candidates exist, roles vote for best candidate; simplified: vote for role with highest confidence
        weighted = {}
        for role, conf in confidence_scores.items():
            w = self.members[role].weight
            weighted[role] = conf * w

        if not weighted:
            return {"winner": "no_consensus", "confidence": 0.3, "votes": {}}

        winner_role = max(weighted, key=lambda k: weighted[k])
        winner_conf = confidence_scores.get(winner_role, 0.5)

        # normalize to confidence 0-1
        total_weight = sum(weighted.values())
        winner_norm = weighted[winner_role] / total_weight if total_weight else 0.5

        return {
            "winner": winner_role,
            "confidence": round(winner_conf, 3),
            "weighted_score": round(winner_norm, 3),
            "votes": weighted,
            "method": "weighted_confidence"
        }

    def _synthesize_final(self, goal: str, proposal: str, analyses: Dict[str, Dict], critic_notes: List[Dict], vote: Dict, evidence_matrix: Dict) -> str:
        winner_role = vote.get("winner", "Researcher")
        winner_analysis = analyses.get(winner_role, {}).get("analysis", "") if winner_role in analyses else ""

        # Synthesis: combine best parts
        parts = []
        parts.append(f"Goal: {goal}")
        parts.append(f"Council decision: {winner_role} leads (confidence {vote.get('confidence', 0.6):.2f}, weighted {vote.get('weighted_score', 0.5):.2f})")
        parts.append(f"Leading analysis: {winner_analysis[:400]}")

        # include verification
        verifier = analyses.get("Verifier", {}).get("analysis", "")
        if verifier:
            parts.append(f"Verification: {verifier[:200]}")

        # include security
        security = analyses.get("Security", {}).get("analysis", "")
        if security:
            parts.append(f"Security: {security[:200]}")

        # evidence summary
        parts.append(f"Evidence: {evidence_matrix.get('total_evidence')} pieces, {evidence_matrix.get('consensus_groups')} consensus groups")

        return "\n\n".join(parts)

    def add_member(self, role: str, bot_name: str, weight: float = 1.0):
        self.members[role] = CouncilMember(role=role, bot_name=bot_name, weight=weight)

    def stats(self) -> Dict[str, Any]:
        return {
            "members": list(self.members.keys()),
            "weights": self.weights,
            "deliberations": "track via episodic if memory linked"
        }
