# JSON to XML Telegram Chat Converter

Convert Telegram chat/channel JSON exports into clean XML with filtering by author/date and optional reactions.

## What this project is for
This tool helps you transform Telegram export JSON into XML that is easier to:
- feed into downstream parsers;
- archive and version;
- run text analytics on.

The project now supports two modes:
- GUI mode (Tkinter): convenient local desktop usage;
- CLI mode: scriptable and automation-friendly (works even when Tkinter is unavailable).
- TUI mode (Textual): modern terminal UI with form-driven workflow (`--tui`).

Modular package entrypoint is also available:
- `python3 -m tgxml ...` (requires `PYTHONPATH=src`)

## Input and output

### Expected input
Telegram export JSON with root fields like:
- `name`, `type`, `id`
- `messages[]`

Each message is expected to follow Telegram export semantics (`type`, `date`, `from`, `text`, optional `reactions`).

### Output format
XML root is always:
- `<messages>`

Each exported message is:
- `<message id="..." date="..." sender="..." [reply_to="..."]>`
- nested `<text>...</text>`
- optional `<reactions><reaction emoji="..." count="..."/></reactions>`

## Features
- Message filtering:
  - by selected authors;
  - by date range (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`).
- Message selection rules:
  - includes only `type == "message"`;
  - skips messages with empty text.
- Extended export options:
  - include Telegram `service` messages;
  - include media metadata (`photo`, `file`, dimensions, MIME, etc.);
  - include `text_entities`;
  - anonymize authors and ids;
  - merge multiple source exports.
- Output controls:
  - include/exclude reactions;
  - human-readable XML (indented) or compact XML.
- Live counters in GUI.
- Interactive CLI wizard and simple command mode.
- Interactive CLI start menu with arrow-key navigation in TTY terminals.
- Dry-run mode with filter diagnostics report.

## Requirements
- Python 3.8+
- For GUI mode: Tkinter installed in Python runtime.

## Run

### GUI mode
```bash
python3 jsontoxml.py
```

If Tkinter is missing, GUI mode will fail with a clear error. Use CLI mode instead.

### CLI mode (simple command)
```bash
python3 jsontoxml.py --cli --run --source exports/ChatExport_2024-12-27/result.json --output exports/out.xml
```

Alternative package run:
```bash
PYTHONPATH=src python3 -m tgxml --cli --run --source exports/ChatExport_2024-12-27/result.json --output exports/out.xml
```

### CLI mode (interactive wizard)
```bash
python3 jsontoxml.py --interactive --source exports/ChatExport_2024-12-27/result.json
```

### TUI mode (Textual)
```bash
python3 jsontoxml.py --tui
```

TUI provides:
- source/form-based options editing;
- inspect, dry-run and export actions;
- keyboard-first navigation with modern terminal UI widgets.

In TTY terminals, interactive mode supports arrow navigation:
- Up/Down to move
- Enter to select
- Space to toggle author in multi-select
- `a` to select all authors
- `q`/Esc to quit current menu

## macOS app packaging

You can package the GUI version as a native `.app` and a single distributable `.zip`:

```bash
./scripts/build_macos_app.sh
```

Build outputs:
- `dist/Telegram JSON XML Converter.app`
- `dist/Telegram_JSON_XML_Converter-macOS.zip`

Notes:
- Build on macOS.
- Current Python runtime must include Tkinter.
- For sharing outside your machine, you may additionally sign/notarize the app.

## CLI reference

### Required for non-interactive mode
- `--source <path>`: source Telegram JSON.

### Output options
- `--output <path>`: exact output XML path.
- `--output-dir <dir>`: output directory (used if `--output` omitted).

### Filtering options
- `--author <name>` (repeatable): include only selected authors.
- `--sources <path1 path2 ...>`: merge multiple source JSON files.
- `--start-date <date>`: lower date bound.
- `--end-date <date>`: upper date bound.
- `--no-date-filter`: disable date filtering.

### Content/format options
- `--no-reactions`: exclude reactions.
- `--compact`: produce compact XML (no pretty indentation).
- `--dry-run`: calculate result without writing XML file.
- `--report-json`: print machine-readable run report.
- `--include-service`: include Telegram service events.
- `--include-media-meta`: include media metadata in XML.
- `--include-entities`: include `text_entities` in XML.
- `--anonymize`: anonymize names and id-like fields.
- `--validate-input`: validate Telegram JSON structure before conversion.
- `--preset <name>` / `--save-preset <name>`: load/save option presets.

### Mode switches
- `--cli`: force CLI mode.
- `--run`: one-shot conversion (non-interactive).
- `--interactive`: run prompt-based CLI wizard.
- `--tui`: run Textual-based terminal UI.

## Examples

### Export all messages (compact XML, no reactions)
```bash
python3 jsontoxml.py --cli \
  --run \
  --source exports/ChatExport_2024-12-27/result.json \
  --output exports/chat_compact.xml \
  --compact \
  --no-reactions \
  --no-date-filter
```

### Export one author for a date window
```bash
python3 jsontoxml.py --cli \
  --run \
  --source exports/ChatExport_2024-12-27/result.json \
  --output exports/chat_filtered.xml \
  --author "Author Name" \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

### Dry-run with JSON report
```bash
python3 jsontoxml.py --cli \
  --run \
  --source exports/ChatExport_2024-12-27/result.json \
  --dry-run \
  --report-json
```

### Merge two exports with anonymization and extended metadata
```bash
python3 jsontoxml.py --cli \
  --run \
  --sources exports/a/result.json exports/b/result.json \
  --output exports/merged.xml \
  --include-service \
  --include-media-meta \
  --include-entities \
  --anonymize \
  --validate-input
```

## Smoke test
Run a quick end-to-end check:
```bash
./scripts/smoke_test.sh
```

What it verifies:
- CLI conversion runs successfully.
- Output XML is created.
- Root tag is `messages`.
- At least one `<message>` exists.

## Project structure
- `jsontoxml.py` - current main entrypoint (GUI + CLI)
- `src/tgxml/core.py` - modular core facade
- `src/tgxml/cli.py` - modular CLI entrypoint
- `src/tgxml/gui.py` - modular GUI entrypoint
- `src/tgxml/models.py` - dataclass models
- `tests/` - unit and e2e tests
- `scripts/smoke_test.sh` - smoke verification
- `scripts/benchmark_large_export.py` - performance baseline
- `docs/modularization-plan.md` - stage-2 modular split plan
- `docs/release-policy.md` - release process
- `legacy/` - archived non-core and historical artifacts
- `exports/` - output artifacts

## Troubleshooting

### `ModuleNotFoundError: No module named '_tkinter'`
Your Python runtime has no Tkinter. Use CLI mode, or install Tkinter for GUI usage.

### `Error: No messages to export`
Likely all messages were filtered out by author/date or empty text filtering.

### Invalid JSON / parse error
Ensure the source file is valid Telegram export JSON and UTF-8 encoded.

### Arrow navigation does not work
Arrow-key menus are enabled only in TTY terminals with curses support.
In non-TTY/CI, CLI automatically falls back to plain text prompts.

### Textual mode does not start
Install Textual:
```bash
python3 -m pip install textual
```

## Product direction
Target quality bar:
- lightweight runtime;
- deterministic filtering and output;
- clear UX in both GUI and CLI;
- easy onboarding via complete documentation.
