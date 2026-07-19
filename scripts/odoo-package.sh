#!/usr/bin/env bash
# Package leadintel_connector for deployment to an Odoo addons path.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/dist/leadintel_connector.zip}"
mkdir -p "$(dirname "$OUT")"
cd "$ROOT/odoo_addons"
rm -f "$OUT"
zip -r "$OUT" leadintel_connector -x "*.pyc" -x "*__pycache__*"
echo "Wrote $OUT"
