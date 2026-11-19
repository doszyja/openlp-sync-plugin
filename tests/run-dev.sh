#!/usr/bin/env bash
# Run OpenLP from monorepo parent or OPENLP_SRC (standalone contrib repo).
set -euo pipefail
CONTRIB_ROOT="$(cd "$(dirname "$0")" && pwd)"
PARENT="$(cd "$(dirname "$CONTRIB_ROOT")" && pwd)"
if [[ -f "$PARENT/run_openlp_dev.py" ]]; then
  LOG_LEVEL="${1:-debug}"
  powershell.exe -ExecutionPolicy Bypass -File "$CONTRIB_ROOT/run-dev.ps1" -LogLevel "$LOG_LEVEL"
else
  export OPENLP_SRC="${OPENLP_SRC:-}"
  bash "$CONTRIB_ROOT/dev/run-with-openlp.sh" "${1:-debug}"
fi