#!/usr/bin/env bash
# Launch PDF Studio (Linux / macOS).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" "$ROOT/run.py"
fi

if command -v python3 >/dev/null 2>&1; then
  echo "No .venv found — run ./scripts/install.sh first (or: python3 run.py with deps installed)."
  exec python3 "$ROOT/run.py"
fi

echo "Python not found. Install Python 3.10+ then run ./scripts/install.sh"
exit 1
