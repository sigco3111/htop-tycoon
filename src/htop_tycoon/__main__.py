"""`python -m htop_tycoon` entry point.

v3.0: instantiates HtopTycoonApp with parsed args and launches the TUI.
`--seed` controls the RNG, `--speed` sets the initial tick rate,
`--headless` runs a short headless smoke test (for CI; exits after
a few ticks).
"""

from __future__ import annotations

import argparse
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
        help="run a short headless smoke test (no TUI, exits after 3 ticks)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"htop-tycoon {__version__}",
    )
    return parser


def _run_headless(seed: int | None, speed: int, max_ticks: int = 3) -> int:
    """Run N ticks headlessly and return 0 on success."""
    from htop_tycoon.domain import Platform
    from htop_tycoon.domain.rng import GameRng
    from htop_tycoon.engine import tick
    from htop_tycoon.engine.market import MarketState
    from htop_tycoon.ui.mock_state import mock_state

    state = mock_state(speed=speed)
    rng = GameRng(seed if seed is not None else state.rng_seed)
    market = MarketState.default_for_platform(Platform.PC)

    print(f"htop-tycoon {__version__} headless smoke test (max_ticks={max_ticks})")
    for tick_num in range(1, max_ticks + 1):
        state = tick(state, rng, market)
        print(
            f"  tick {tick_num}: day={state.day_index} cash={state.cash.cents // 100}"
        )
    print(f"Headless smoke complete: {len(state.employees)} employees, "
          f"{len(state.projects)} projects, {len(state.event_log)} events")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.headless:
        return _run_headless(args.seed, args.speed)

    from htop_tycoon.domain.rng import GameRng
    from htop_tycoon.engine import DEFAULT_MARKET
    from htop_tycoon.ui.app import HtopTycoonApp
    from htop_tycoon.ui.mock_state import mock_state

    state = mock_state(speed=args.speed)
    rng = GameRng(args.seed if args.seed is not None else state.rng_seed)
    app = HtopTycoonApp(state=state, rng=rng, market=DEFAULT_MARKET)
    return app.run() or 0


if __name__ == "__main__":
    raise SystemExit(main())
