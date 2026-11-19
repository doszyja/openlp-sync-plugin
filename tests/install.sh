#!/usr/bin/env bash
# Install Song Stats community plugin into the OpenLP data directory (Linux/macOS).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_CONTRIB="${OPENLP_DATA:-$HOME/.local/share/openlp}/contrib"

if [[ "$(uname -s)" == "Darwin" ]]; then
  TARGET_CONTRIB="${OPENLP_DATA:-$HOME/Library/Application Support/openlp/Data}/contrib"
fi

mkdir -p "$TARGET_CONTRIB"
cp -a "$SCRIPT_DIR/__init__.py" "$TARGET_CONTRIB/"
cp -a "$SCRIPT_DIR/plugins" "$TARGET_CONTRIB/"

echo "Zainstalowano wtyczkę KWCH (katalog: $TARGET_CONTRIB/plugins/songstats)"
echo "Zrestartuj OpenLP → Ustawienia → Zarządzaj wtyczkami → włącz „KWCH Swietochlowice plugin”."