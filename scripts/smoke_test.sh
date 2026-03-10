#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_JSON="$ROOT_DIR/exports/ChatExport_2024-12-27/result.json"
OUT_XML="$ROOT_DIR/exports/smoke_test.xml"

if [[ ! -f "$SRC_JSON" ]]; then
  echo "[smoke] source not found: $SRC_JSON" >&2
  exit 1
fi

mkdir -p "$ROOT_DIR/exports"
python3 "$ROOT_DIR/jsontoxml.py" --cli \
  --run \
  --source "$SRC_JSON" \
  --output "$OUT_XML" \
  --compact \
  --no-date-filter

python3 - <<'PY'
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

path = Path("/Users/andrewsuhantsev/programming/json-to-xml-tgchat/exports/smoke_test.xml")
if not path.exists():
    print("[smoke] xml output file was not created", file=sys.stderr)
    raise SystemExit(1)

root = ET.parse(path).getroot()
if root.tag != "messages":
    print(f"[smoke] unexpected root tag: {root.tag}", file=sys.stderr)
    raise SystemExit(1)

count = len(root.findall("message"))
if count == 0:
    print("[smoke] xml contains zero messages", file=sys.stderr)
    raise SystemExit(1)

print(f"[smoke] ok: {count} messages in {path}")
PY
