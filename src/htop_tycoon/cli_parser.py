"""htop_tycoon.cli_parser — argparse surface for the T30 CLI entry point.

Locks the 7 frozen CLI flags from ``.omo/plans/htop-tycoon.md`` line 653-670:

- ``--seed INT``
- ``--tick-rate FLOAT``
- ``--load PATH``
- ``--no-autosave``
- ``--dev``
- ``--ending ENDING_TYPE``
- ``--ticks N``

Plus the conventional ``--help`` and ``--version`` flags.

This module owns ONLY the parser surface; argument resolution and
dispatch live in :mod:`htop_tycoon.__main__`. Splitting the parser from
the dispatcher keeps each module under the 250 LOC ceiling and lets the
parser be unit-tested without importing the engine / Textual stack.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from htop_tycoon import __version__
from htop_tycoon.domain.ending import EndingType

__all__ = ["_ENDING_CHOICES", "_build_parser"]


# Choices for ``--ending``: the 5 locked ``EndingType`` values. We lock them
# here (not at runtime via ``EndingType.__members__``) so the help text is
# deterministic across Python versions and the frozen test set can pin
# them in T33.
_ENDING_CHOICES: tuple[str, ...] = (
    EndingType.BANKRUPTCY.value,
    EndingType.IPO.value,
    EndingType.HOSTILE_MA.value,
    EndingType.VOLUNTARY_SALE.value,
    EndingType.SECRET.value,
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the locked argparse parser with all 7 frozen flags.

    The parser is deliberately permissive: it does NOT reject negative
    ``--ticks`` at parse time (argparse's ``type=int`` accepts them).
    Negative ticks are rejected in :func:`htop_tycoon.__main__._run_headless`
    where the error has a CLI exit-code context. Invalid ``--ending``
    values are rejected at parse time via ``choices=_ENDING_CHOICES``.
    """
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
        metavar="INT",
        help=(
            "RNG seed for the new game (ignored when --load is given). "
            "Default: int(time.time()) when not loading. "
            "Use this flag in tests for deterministic runs."
        ),
    )
    parser.add_argument(
        "--tick-rate",
        type=float,
        default=None,
        metavar="FLOAT",
        help=(
            "Real seconds per game tick (1 tick = 1 game week per AGENTS.md). "
            "Default: balance.yaml time.seconds_per_tick."
        ),
    )
    parser.add_argument(
        "--load",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to a save file to load. "
            "Default: $XDG_DATA_HOME/htop-tycoon/save.json if it exists."
        ),
    )
    parser.add_argument(
        "--no-autosave",
        action="store_true",
        help="Disable autosave (for tests and deterministic runs).",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable the Textual dev console (development only).",
    )
    parser.add_argument(
        "--ending",
        type=str,
        choices=_ENDING_CHOICES,
        default=None,
        metavar="ENDING_TYPE",
        help=(
            "Force-trigger a specific ending at the --ticks boundary. "
            "Used by T33 for deterministic ending screenshot capture. "
            f"Choices: {', '.join(_ENDING_CHOICES)}."
        ),
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Advance exactly N ticks via the engine and exit (no UI). "
            "Used for deterministic CLI testing and CI evidence capture."
        ),
    )
    return parser
