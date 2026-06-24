"""CLI entry point for htop-tycoon.

Full flag set is implemented in T30. This stub launches the basic skeleton so
``python -m htop_tycoon --help`` works from day 1.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from htop_tycoon import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="htop-tycoon",
        description=(
            "htop-styled TUI business simulator. CPU=revenue, memory=inventory, "
            "swap=debt, zombie=resigning employees. 5 endings, Korean UI."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for deterministic simulation (T30: full wiring).",
    )
    parser.add_argument(
        "--tick-rate",
        type=float,
        default=None,
        help="Real seconds per game tick (1 tick = 1 game week). T30: full wiring.",
    )
    parser.add_argument(
        "--load",
        type=Path,
        default=None,
        help="Path to a save file to load. T30: full wiring.",
    )
    parser.add_argument(
        "--no-autosave",
        action="store_true",
        help="Disable autosave (for tests and deterministic runs). T30: full wiring.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    # T30 will wire these into TickEngine + HtopTycoonApp.
    # T1 only verifies argparse + version flag.
    print(
        f"htop-tycoon {__version__} - skeleton CLI (full app in T16, T30)",
        file=sys.stderr,
    )
    print(f"parsed: {vars(args)}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
