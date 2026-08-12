# Vortex 1.0 — Frozen architecture

This nine-layer layout is **frozen**. Do not add a tenth control layer unless a real workload proves a missing capability.

```
1. Infrastructure
2. Memory
3. Orchestration
4. Council
5. Resolution
6. Governance
7. Sovereign
8. API
9. Interface
```

Request path (cannot be bypassed for `agent.chat`):

```
Interface → API → Sovereign → Governance → Orchestration
  → Council? → Resolution → Tools → Memory ↔ Knowledge Graph
  → Observability → Evaluation → Self-Improvement
```

Evolution path (never writes production source):

```
stable → isolated git worktree → patch → tests → benchmark
  → security → council/resolution → governance → canary
  → promote only if V(n+1) > V(n) → monitor → rollback
```

Promotion requires: tests PASS, security PASS, benchmark > stable, critical regressions = 0, governance ALLOW, canary PASS.

Voice/phone remains a later interface. The brain is frozen at 1.0.
