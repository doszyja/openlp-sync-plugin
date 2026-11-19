#!/usr/bin/env bash
# Install contrib from this repo, then start OpenLP from OPENLP_SRC.
set -euo pipefail
CONTRIB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPENLP_SRC="${OPENLP_SRC:-}"
if [[ -z "$OPENLP_SRC" && -f "$(dirname "$CONTRIB_ROOT")/run_openlp_dev.py" ]]; then
  OPENLP_SRC="$(cd "$(dirname "$CONTRIB_ROOT")" && pwd)"
fi
if [[ -z "$OPENLP_SRC" || ! -f "$OPENLP_SRC/run_openlp_dev.py" ]]; then
  echo "Set OPENLP_SRC to OpenLP checkout (with run_openlp_dev.py)." >&2
  exit 1
fi
bash "$CONTRIB_ROOT/install.sh"
cd "$OPENLP_SRC"
exec python3 run_openlp_dev.py -l "${1:-debug}"