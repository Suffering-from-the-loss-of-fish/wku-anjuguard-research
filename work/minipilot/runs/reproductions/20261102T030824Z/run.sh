#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
ACTION="${1:-help}"
if [[ "$ACTION" == setup ]]; then
  PILOT_PYTHON="${PILOT_PYTHON:-/Users/wangkai/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
  if [[ ! -x "$PILOT_PYTHON" ]]; then PILOT_PYTHON="$(command -v python3.12 || command -v python3)"; fi
  "$PILOT_PYTHON" -m venv .venv
  .venv/bin/python -m pip install -r requirements.lock
  exit 0
fi
if [[ "$ACTION" == help ]]; then
  cat <<'HELP'
Usage: ./run.sh setup | smoke | real | recompute | provenance
setup       Install exact Python dependencies (Apple Silicon macOS, Python 3.12).
smoke       Run clearly synthetic/unit workflow tests. No network or real model.
real        Download pinned public data/models; run both directions in a NEW run directory.
recompute   Re-evaluate the delivered recorded predictions, without model calls.
provenance  Save source/model/environment hashes. No secret values are collected.
All real failures remain failures. No command falls back to mock model outputs.
HELP
  exit 0
fi
if [[ ! -x .venv/bin/python ]]; then echo 'Run ./run.sh setup first.' >&2; exit 2; fi
case "$ACTION" in
  smoke) .venv/bin/python -m pytest -q tests ;;
  real) .venv/bin/python pilot/run_real.py ;;
  recompute) .venv/bin/python pilot/recompute.py ;;
  provenance) .venv/bin/python pilot/provenance.py ;;
  *) echo "Unknown action: $ACTION" >&2; exit 2 ;;
esac
