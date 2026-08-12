---
name: research
description: Multi-step web research and structured report writing
tags: research, web, report
source: bundled
---

# Research skill

When the user asks to research, investigate, analyze, or write a report:

1. **Clarify the topic** — extract the core subject from the goal.
2. **Search** — call `web_search` with a focused query (max_results 5).
3. **Deepen** — if results include real URLs, `http_fetch` the best one.
4. **Synthesize** — write a markdown report via `write_file` to `reports/<slug>.md` with:
   - Title / Goal
   - Findings (bullets + source snippets)
   - Conclusion
5. **Remember** — `memory_store` a short summary tagged `research`.
6. **Finish** — return a concise summary pointing at the workspace path.

Do not invent citations. Prefer tool observations over prior knowledge when tools succeed.
