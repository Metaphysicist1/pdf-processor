#!/usr/bin/env bash
# Install PDF Studio deps into a local .venv (Linux / macOS).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3 not found. Install Python 3.10+ and retry."
  exit 1
fi

echo "==> Creating virtual environment (.venv)"
"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "Done. Start the app with:"
echo "  ./scripts/run.sh"
echo "  or:  source .venv/bin/activate && python run.py"
echo
echo "Optional — add to your app menu:"
echo "  ./scripts/install_desktop_linux.sh"
