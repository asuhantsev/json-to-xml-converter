#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_NAME="Telegram JSON XML Converter"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"
ZIP_PATH="$DIST_DIR/${APP_NAME// /_}-macOS.zip"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[build] This script is intended for macOS only." >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/venv/bin/python"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[build] Python not found: $PYTHON_BIN" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c "import tkinter" >/dev/null 2>&1; then
  echo "[build] Tkinter is missing in current Python runtime. Install Tkinter first." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1; then
  echo "[build] PyInstaller is not installed. Installing..."
  "$PYTHON_BIN" -m pip install --upgrade pyinstaller
fi

rm -rf "$DIST_DIR" "$BUILD_DIR"

echo "[build] Building macOS .app..."
"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  jsontoxml.py

APP_PATH="$DIST_DIR/$APP_NAME.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "[build] Expected app bundle not found: $APP_PATH" >&2
  exit 1
fi

echo "[build] Packaging app into single zip file..."
rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

echo "[build] Done"
echo "[build] App: $APP_PATH"
echo "[build] Zip: $ZIP_PATH"
