#!/usr/bin/env python3
"""Vortex Agent interactive CLI (Hermes-style cli.py at repo root)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vortex_cli.main import main  # noqa: E402


if __name__ == "__main__":
    main()
    sys.exit(0)
