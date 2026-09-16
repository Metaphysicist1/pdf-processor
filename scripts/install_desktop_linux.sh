#!/usr/bin/env bash
# Install a desktop menu entry that launches PDF Studio on Linux.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APP_DIR"

# Prefer the packaged binary if present; otherwise the run script.
if [[ -x "$ROOT/dist/PDFStudio" ]]; then
  EXEC="$ROOT/dist/PDFStudio"
else
  EXEC="$ROOT/scripts/run.sh"
fi

cat > "$APP_DIR/pdf-studio.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=PDF Studio
GenericName=PDF Toolkit
Comment=Merge, compress, strip metadata, remove pages, and convert PDFs
Exec=$EXEC
Path=$ROOT
Icon=$ROOT/assets/logo.png
Terminal=false
Categories=Office;
Keywords=PDF;merge;compress;metadata;carousel;Instagram;LinkedIn;
StartupNotify=true
EOF

chmod +x "$APP_DIR/pdf-studio.desktop"
chmod +x "$ROOT/scripts/run.sh" 2>/dev/null || true
update-desktop-database "$APP_DIR" 2>/dev/null || true

echo "Installed: $APP_DIR/pdf-studio.desktop"
echo "Search your app menu for: PDF Studio"
echo "Launch path: $EXEC"
