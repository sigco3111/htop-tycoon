"""CLI entry point for htop-tycoon — full T30 flag set + headless ``--ticks`` mode.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 653-670:

- argparse with 7 frozen flags (parser lives in :mod:`htop_tycoon.cli_parser`):
    - ``--seed INT`` (default = ``int(time.time())`` if not loading — the test
      controls this via explicit ``--seed``)
    - ``--tick-rate FLOAT`` (default = ``balance["time"]["seconds_per_tick"]``)
    - ``--load PATH`` (default = XDG path if it exists)
    - ``--no-autosave`` (disable autosave for testing)
    - ``--dev`` (enable textual dev console)
    - ``--ending ENDING_TYPE`` (T33 screenshot capture — force-trigger ending
      at ``--ticks`` boundary)
    - ``--ticks N`` (testing — advance exactly N ticks then exit, no UI)
- ``main()`` parses args, loads or creates a state, then either:
    1. ``--ticks N`` mode: advance N ticks via the ``TickEngine``, optionally
       apply the forced ``--ending``, print the final state_hash as JSON, and
       exit. NO UI is launched (CI-friendly).
    2. UI mode: launch ``HtopTycoonApp`` with the resolved seed/tick_rate/
       no_autosave and the loaded/created state.
- The XDG save path is ``$XDG_DATA_HOME/htop-tycoon/save.json`` (or
  ``~/.local/share/htop-tycoon/save.json`` when ``XDG_DATA_HOME`` is unset),
  per the FreeDesktop XDG Base Directory Specification referenced in the
  T29 acceptance criteria.

The frozen state_hash at ``(seed=42, ticks=5)`` is locked in
``tests/test_cli.py`` as the determinism contract for the CLI layer.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from htop_tycoon.cli_parser import _build_parser
from htop_tycoon.data import load_balance
from htop_tycoon.domain.ending import EndingType
from htop_tycoon.domain.state import GameState, new_game, state_hash
from htop_tycoon.engine.ending import apply_ending
from htop_tycoon.engine.tick import TickEngine
from htop_tycoon.persistence.deserialize import load as persistence_load
from htop_tycoon.ui.app import HtopTycoonApp

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# XDG save path resolution.
#
# Per the FreeDesktop XDG Base Directory Specification:
#   - If ``$XDG_DATA_HOME`` is set and non-empty, use it as the base.
#   - Else use ``$HOME/.local/share``.
# The directory is NOT created here; this is a pure path computation. The
# caller (T29 autosave, or the CLI's load path) decides whether to create
# the directory.
# ---------------------------------------------------------------------------

_XDG_SUBDIR = "htop-tycoon"
_XDG_SAVE_FILENAME = "save.json"


def default_xdg_save_path() -> Path:
    """Return the default XDG save path: ``$XDG_DATA_HOME/htop-tycoon/save.json``.

    Pure path computation; does NOT touch the filesystem.

    Returns:
        The default save path. The directory may or may not exist; callers
        are responsible for ``exists()`` checks and/or ``mkdir``.
    """
    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        base = Path(xdg_data_home)
    else:
        base = Path.home() / ".local" / "share"
    return base / _XDG_SUBDIR / _XDG_SAVE_FILENAME


# ---------------------------------------------------------------------------
# Argument resolution helpers — pure functions over the parsed namespace.
# ---------------------------------------------------------------------------


def _resolve_tick_rate(args: argparse.Namespace) -> float:
    """Return the effective tick rate.

    Priority:
        1. ``args.tick_rate`` if explicitly set.
        2. ``balance["time"]["seconds_per_tick"]`` (the YAML constant).
        3. ``1.0`` fallback if balance.yaml is unreadable.
    """
    if args.tick_rate is not None:
        return cast(float, args.tick_rate)
    try:
        return float(load_balance()["time"]["seconds_per_tick"])
    except (KeyError, TypeError, ValueError) as exc:
        _logger.warning("balance.yaml unreadable for tick rate (%s); using 1.0", exc)
        return 1.0


def _resolve_seed(args: argparse.Namespace) -> int:
    """Return the effective seed: ``--seed`` if given, else ``int(time.time())``.

    The time-based default is acceptable here per AGENTS.md: this is the
    CLI's NEW-GAME seed, not a recovery seed. The determinism invariant
    applies to recovery seeds (``CORRUPTION_RECOVERY_SEED = 0`` is the
    locked constant), not to "the user didn't specify a seed" — that is
    an explicit non-deterministic scenario.
    """
    if args.seed is not None:
        return cast(int, args.seed)
    return int(time.time())


def _resolve_state(args: argparse.Namespace) -> GameState:
    """Load or create the initial ``GameState`` per the locked priority.

    Priority:
        1. ``--load PATH``: load from that path. On error
           (``FileNotFoundError``, corrupt JSON, etc.) the persistence
           layer's corruption-recovery path returns a recovery state.
        2. Else if the default XDG path exists: load from it.
        3. Else: create ``new_game(seed)`` with the resolved seed.
    """
    if args.load is not None:
        return persistence_load(args.load)

    xdg_default = default_xdg_save_path()
    if xdg_default.exists():
        return persistence_load(xdg_default)

    return new_game(_resolve_seed(args))


def _apply_ending_if_requested(
    state: GameState, ending_value: str | None
) -> GameState:
    """Apply the forced ending if ``--ending`` was given.

    The forced ending is appended to ``ending_history`` via
    ``engine.ending.apply_ending`` and emitted as an ``EndingTriggered``
    event. Per plan line 660, this is the T33 screenshot-capture hook:
    it lets tests deterministically land on a specific ending at the
    ``--ticks`` boundary.

    Returns the input state unchanged when ``ending_value`` is ``None``.
    """
    if ending_value is None:
        return state
    ending_type = EndingType(ending_value)
    new_state, _events = apply_ending(state, ending_type)
    return new_state


# ---------------------------------------------------------------------------
# Entry-point paths: headless (``--ticks N``) vs. UI launch.
# ---------------------------------------------------------------------------


def _run_headless(args: argparse.Namespace) -> int:
    """Run ``--ticks N`` headless: load/create state, advance N ticks, print JSON.

    No Textual App is constructed; this path is CI-safe (no TTY required).
    The JSON line on stdout is the deterministic evidence artifact used by
    ``tests/test_playthrough.py`` (T32) and the QA scenarios.

    Returns the exit code (0 on success, non-zero on validation error).
    """
    if args.ticks is None:
        # Defensive: caller already gated on ``args.ticks is not None``.
        return 2
    if args.ticks < 0:
        # argparse ``type=int`` accepts negatives; we reject them here.
        _logger.error("--ticks must be >= 0, got %d", args.ticks)
        return 2

    state = _resolve_state(args)
    if args.ticks > 0:
        # Use the state's ``rng_seed`` so the engine's RNG stream matches
        # the state we just resolved (loaded or freshly created). For new
        # games, ``state.rng_seed`` is the seed we just used. For loaded
        # games, it's the seed the game was originally started with —
        # this is what makes ``--load --ticks N`` reproducible.
        engine_seed = state.rng_seed
        engine = TickEngine(engine_seed)
        state = engine.advance(state, args.ticks)

    state = _apply_ending_if_requested(state, args.ending)

    payload = {
        "tick": state.tick,
        "hash": state_hash(state),
        "rng_seed": state.rng_seed,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


def _run_app(args: argparse.Namespace) -> int:
    """Launch the Textual ``HtopTycoonApp``.

    The App is constructed with the resolved seed/tick_rate/no_autosave so
    its ``TickEngine`` and ``EventBus`` are wired correctly. When the
    initial state was loaded (from ``--load`` or XDG), we rebind
    ``app.state`` and re-construct ``app.engine`` so the loaded state is
    authoritative — per AGENTS.md "State boundary": the engine is the
    only writer, but the initial rebind here is the legitimate
    bootstrap hook.
    """
    state = _resolve_state(args)
    tick_rate = _resolve_tick_rate(args)

    app = HtopTycoonApp(
        seed=state.rng_seed,
        tick_rate=tick_rate,
        no_autosave=args.no_autosave,
    )
    # Rebind to the resolved state (which may be loaded, not freshly
    # created). The App's ``__init__`` called ``new_game(seed)`` which
    # gives tick=0; we replace it with the loaded state and rewire the
    # engine so its RNG stream matches the loaded state's seed.
    app.state = state
    app.engine = TickEngine(state.rng_seed)

    return app.run() or 0


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """T30: full CLI entry point — 7 frozen flags + headless ``--ticks`` mode.

    Dispatches to ``_run_headless`` when ``--ticks`` is given, otherwise
    to ``_run_app``. Returns the exit code; on argparse errors the
    ``SystemExit`` raised by argparse propagates (per argparse convention).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.ticks is not None:
        return _run_headless(args)
    return _run_app(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
