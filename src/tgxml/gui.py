"""GUI entrypoints for tgxml."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jsontoxml import ConversionGUI, tk


def run_gui():
    if tk is None:
        raise RuntimeError(
            "Tkinter is not available in this Python environment. "
            "Use CLI mode instead."
        )
    app = ConversionGUI()
    app.run()


__all__ = ["run_gui", "ConversionGUI"]
