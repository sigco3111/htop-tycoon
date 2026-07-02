"""`python -m htop_tycoon` entry point.

Phase 1: only `--help` and `--version` are real surfaces. `--seed`, `--speed`,
`--headless` are declared but unimplemented (Phase 2+).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from htop_tycoon import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="htop-tycoon",
        description=(
            "htop-style TUI port of Kairosoft Game Dev Story (v3.0). "
            "Pick a Strategy Manager and watch the AI run your studio."
        ),
        epilog="See README.md for key bindings and CLI flags.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="deterministic seed for the RNG (default: random)",
    )
    parser.add_argument(
        "--speed",
        type=int,
        default=1,
        choices=[0, 1, 2, 3, 4],
        help="initial game speed (0=paused, 1-3=user, 4=headless QA)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without TUI for QA (Phase 2+; ignored in Phase 1)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"htop-tycoon {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns process exit code."""
    parser = _build_parser()
    parser.parse_args(argv)

    # Phase 1: --help / --version are the only verified surfaces.
    # Phase 2 will instantiate HtopTycoonApp with parsed args and .run().
    print(
        f"htop-tycoon {__version__} — Phase 1 scaffolding only. "
        "Use --help to see available flags. The TUI will launch in Phase 2+.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
