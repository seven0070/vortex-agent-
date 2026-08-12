#!/usr/bin/env bash
# Build + smoke-test Vortex Agent
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "══ Vortex Agent build ══"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q -e .

echo "── doctor ──"
python -m vortex doctor

echo "── import check ──"
python - <<'PY'
from vortex import NAME, VERSION
from vortex.agent.os import VortexOS
from vortex.tools.registry import registry
import vortex.tools
os_ = VortexOS()
assert NAME == "Vortex Agent"
assert len(os_.council.list_seats()) == 24
assert len(registry.names()) >= 18
print(f"{NAME} v{VERSION} · seats={len(os_.council.list_seats())} tools={len(registry.names())}")
print("BUILD_OK")
PY

echo "══ done ══"
echo "Run:  source .venv/bin/activate && python run.py"
