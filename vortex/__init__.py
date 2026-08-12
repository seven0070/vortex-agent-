"""Vortex Agent package facade (install name) over Hermes-style top-level layout.

External structure mirrors Hermes Agent:

  agent/          core loop, council, chamber, memory
  tools/          self-registering tools
  toolsets.py     named tool groups
  gateway/        API + messaging waist
  vortex_cli/     CLI subcommands
  skills/         SKILL.md playbooks
  cron/           scheduler extension point
  plugins/        memory/platform plugins
  apps/           Mission Control UI
  run_agent.py    root one-shot runner
  cli.py          root interactive CLI
"""
from vortex_constants import NAME, VERSION, TAGLINE

__all__ = ["NAME", "VERSION", "TAGLINE"]
__version__ = VERSION
__title__ = NAME
