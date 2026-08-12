"""python -m vortex  |  vortex  |  vortex-agent

Usage:
  python -m vortex                 # Mission Control API+UI on :8765
  python -m vortex 9000            # custom port
  python -m vortex cli             # interactive CLI
  python -m vortex doctor          # environment check
  python -m vortex version
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is importable when run as a script path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _version() -> None:
    from vortex.constants import NAME, VERSION, TAGLINE

    print(f"{NAME} v{VERSION}")
    print(TAGLINE)


def _doctor() -> int:
    from vortex.constants import NAME, VERSION, VORTEX_HOME, WORKSPACE, ensure_home
    from vortex.agent.os import VortexOS
    from vortex.tools.registry import registry
    import vortex.tools  # noqa: F401

    ensure_home()
    print(f"🩺 {NAME} doctor")
    print(f"  version   : {VERSION}")
    print(f"  home      : {VORTEX_HOME}")
    print(f"  workspace : {WORKSPACE}")
    print(f"  python    : {sys.version.split()[0]}")
    try:
        os_ = VortexOS()
        print(f"  bots      : {len(os_.bots)} ({', '.join(os_.bots)})")
        print(f"  seats     : {len(os_.council.list_seats())}")
        print(f"  tools     : {len(registry.names())}")
        print(f"  brain     : {os_.brain.provider}")
        print(f"  chamber   : {'on' if os_.council.seat_worker_factory else 'off'}")
        # tiny smoke
        r = os_.agent.run("Calculate 1+1", background=False, max_steps=4)
        ok = r.get("status") == "completed"
        print(f"  smoke     : {'pass' if ok else 'fail'} ({r.get('status')})")
        print("OK" if ok else "FAIL")
        return 0 if ok else 1
    except Exception as e:
        print(f"  error     : {e}")
        return 1


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        from vortex.gateway.api import main as api_main

        api_main([])
        return

    cmd = argv[0]
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return
    if cmd in ("-V", "--version", "version"):
        _version()
        return
    if cmd == "doctor":
        raise SystemExit(_doctor())
    if cmd in ("cli", "tui", "shell"):
        from vortex.cli.main import main as cli_main

        sys.argv = [sys.argv[0], *argv[1:]]
        cli_main()
        return
    if cmd in ("serve", "api", "ui"):
        from vortex.gateway.api import main as api_main

        api_main(argv[1:])
        return

    # bare port number → serve
    if cmd.isdigit():
        from vortex.gateway.api import main as api_main

        api_main(argv)
        return

    print(f"Unknown command: {cmd}\n")
    print(__doc__)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
