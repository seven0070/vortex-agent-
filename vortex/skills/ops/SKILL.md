---
name: ops
description: System intel, workspace inspection, shell allowlist ops
tags: ops, shell, workspace
source: bundled
---

# Ops skill

1. System info → `terminal` with `uname -a && whoami && df -h / | tail -1`
2. Workspace listing → `list_files`
3. Find content → `search_files` with a regex
4. Read/write only inside the Vortex workspace
5. Never attempt blocked destructive commands; if denied, explain and pivot
