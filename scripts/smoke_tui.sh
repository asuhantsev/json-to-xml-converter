#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
import importlib.util
import sys

if importlib.util.find_spec("textual") is None:
    print("[tui-smoke] skipped: textual is not installed")
    sys.exit(0)

from src.tgxml.tui_app import TgXmlTextualApp

app_cls = TgXmlTextualApp().build()
assert app_cls is not None
print("[tui-smoke] ok: Textual app class built")
PY
