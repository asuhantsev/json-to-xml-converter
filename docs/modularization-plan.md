# Modularization Plan (Stage 2)

## Goal
Split the current monolithic `jsontoxml.py` into small modules without changing behavior.

## Target structure
- `src/tgxml/core.py`
  - Pure logic: text normalization, filtering, XML tree building, file conversion.
- `src/tgxml/cli.py`
  - Argparse + interactive wizard.
- `src/tgxml/gui.py`
  - Tkinter UI that uses core functions.
- `src/tgxml/models.py`
  - Dataclasses for conversion options and conversion results.
- `src/tgxml/__main__.py`
  - Unified entrypoint.

## Migration steps
1. Extract pure functions from `jsontoxml.py` into `core.py`.
2. Move CLI from `jsontoxml.py` into `cli.py`, keep same flags.
3. Move `ConversionGUI` into `gui.py` with minimal behavioral changes.
4. Introduce `ConversionOptions` dataclass and pass it through core.
5. Add simple unit tests for `core.py`.
6. Keep backward-compatible launcher (`jsontoxml.py` imports and delegates).

## Non-goals
- No redesign of XML schema.
- No UI redesign.
- No change in default filtering semantics.

## Done criteria
- Same output on sample exports before/after split.
- GUI and CLI both work from one entrypoint.
- Smoke test passes.
