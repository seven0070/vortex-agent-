#!/usr/bin/env python3
"""Vortex Agent entrypoint (repo checkout).

  python run.py              # Mission Control UI + API on :8765
  python run.py 9000         # custom port
  python run.py cli          # interactive CLI
  python run.py doctor       # environment check
  python run.py version
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vortex.__main__ import main  # noqa: E402


if __name__ == "__main__":
    main()
