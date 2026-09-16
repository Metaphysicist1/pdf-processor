#!/usr/bin/env bash
# Build a single-file Linux binary with PyInstaller.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "Run ./scripts/install.sh first."
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install pyinstaller
pyinstaller --noconfirm packaging/PDFStudio.spec

echo
echo "Done: dist/PDFStudio"
echo "Run it with:  ./dist/PDFStudio"
echo "Optional menu entry:  ./scripts/install_desktop_linux.sh"
