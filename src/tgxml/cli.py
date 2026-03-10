"""CLI entrypoints for tgxml."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jsontoxml import _parse_cli_args, run_cli


def main(argv=None):
    args = _parse_cli_args(list(sys.argv[1:] if argv is None else argv))
    run_cli(args)


if __name__ == "__main__":
    main()
