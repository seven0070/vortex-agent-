#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "══ Vortex Agent build (Hermes layout) ══"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q -e .

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "── layout check ──"
for d in agent tools gateway vortex_cli skills apps/mission-control cron plugins; do
  [[ -d "$d" ]] || { echo "missing $d"; exit 1; }
  echo "  ✓ $d"
done
for f in run_agent.py cli.py toolsets.py model_tools.py vortex_constants.py run.py; do
  [[ -f "$f" ]] || { echo "missing $f"; exit 1; }
  echo "  ✓ $f"
done

echo "── doctor ──"
python -m vortex doctor

echo "── one-shot ──"
python run_agent.py "Calculate 2+2" | head -20

echo "══ BUILD_OK ══"
echo "Run: source .venv/bin/activate && python run.py"
