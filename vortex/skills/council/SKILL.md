---
name: council
description: Convene the multi-project AI Agent Council (14 seats including LifeOS, Opik, DSPy, Kitesurf)
tags: council, multi-agent, hermes, agent-zero, eve, openworker, lifeos, opik, dspy
source: bundled
---

# Agent Council skill

The council seats are **inspired by real open-source agent projects**. They deliberate; Vortex's autonomous chief executes.

## Members

| Seat | Project |
|------|---------|
| ♟ Prime | [Avyayalaya/agent-prime](https://github.com/Avyayalaya/agent-prime) |
| 🖥 Zero | [agent0ai/agent-zero](https://github.com/agent0ai/agent-zero) |
| 🐝 Buzz | [block/buzz](https://github.com/block/buzz) |
| ☤ Hermes | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) |
| 🏢 QM | [yc-software/qm](https://github.com/yc-software/qm) |
| 📁 Eve | [vercel/eve](https://github.com/vercel/eve) |
| 🗺 Odysseus | [odysseus-dev/odysseus](https://github.com/odysseus-dev/odysseus) |
| 👷 OpenWorker | [andrewyng/openworker](https://github.com/andrewyng/openworker) |
| ⚡ Grok | [xai-org/grok-build](https://github.com/xai-org/grok-build) |
| 📓 Notebook | research synthesizer |
| ⛰ LifeOS | [danielmiessler/LifeOS](https://github.com/danielmiessler/LifeOS) |
| 🔭 Opik | [comet-ml/opik](https://github.com/comet-ml/opik) |
| 🧬 DSPy | [stanfordnlp/dspy](https://github.com/stanfordnlp/dspy) |
| ☁ Kitesurf | [kitesurf.cloudflare.app](https://kitesurf.cloudflare.app) |

## When to convene

- Multi-domain goals (research + build + secure)
- User says council / deliberate / debate / pros and cons
- Architecture, eval, or life/work hill-climb decisions
- High-stakes plans that need adversarial + observability review

## How

```
convene_council(goal="...", auto_execute=true)
```

Optional seats filter (comma-separated ids):
`prime,zero,buzz,hermes,qm,eve,odysseus,openworker,grok,notebook,lifeos,opik,dspy,kitesurf`

## Pipeline

1. **Brief** — each project seat frames the goal  
2. **Propose** — builders + synthesizers (incl. LifeOS, DSPy, Opik, Kitesurf)  
3. **Critique** — Prime gate + Opik eval + DSPy modularity + Buzz collab + evidence  
4. **Vote** — weighted; Prime/Hermes hard-veto on harm  
5. **Execute** — Vortex chief runs the consensus with tools  

## Do not

- Don't convene for trivial single-tool math unless the user asks
- Don't re-enter council from the post-vote executor (blocked)
