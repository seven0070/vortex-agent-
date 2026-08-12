#!/usr/bin/env python3
"""Vortex Agent entrypoint: `python run.py` (API) or `python run.py cli`."""
import sys
from pathlib import Path

# ensure repo root on path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main():
    args = sys.argv[1:]
    if args and args[0] in ("cli", "tui", "shell"):
        from vortex.cli.main import main as cli_main
        sys.argv = [sys.argv[0], *args[1:]]
        cli_main()
    else:
        from vortex.gateway.api import main as api_main
        api_main(args)

if __name__ == "__main__":
    main()
