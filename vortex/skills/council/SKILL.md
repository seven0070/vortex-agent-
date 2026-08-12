---
name: council
description: Convene the AI Agent Council for multi-stakeholder deliberation before execution
tags: council, deliberate, vote, multi-agent
source: bundled
---

# Agent Council skill

Use the council when the goal is **high-stakes**, **multi-domain**, or needs **adversarial review**.

## When to convene

- Strategy + research + build + risk in one goal
- User says deliberate / debate / council / pros and cons / should we
- Architecture or security decisions
- Anything where a single agent might tunnel-vision

## How

1. Call `convene_council` with the full goal.
2. Optional: pass `seats` as comma-separated ids:
   `strategist,researcher,architect,critic,ethicist,cipher,executor`
3. Leave `auto_execute=true` unless the user only wants a verdict.

## Pipeline the council runs

1. **Brief** — each seat frames the goal through its lens  
2. **Propose** — strategist / researcher / architect / executor / cipher draft plans  
3. **Critique** — critic + ethicist + cipher red-team the plans  
4. **Vote** — weighted approve / amend / reject  
5. **Execute** — autonomous chief runs the consensus directive with tools  

## Do not

- Do not convene the council for trivial arithmetic or single-tool tasks
- Do not re-convene from inside a post-council executor (blocked)
