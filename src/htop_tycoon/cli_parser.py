"""htop-tycoon v3.0 — CLI entry point (spec §7.7).

Two modes:

- **Interactive** (default): launch the TUI ``HtopTycoonApp``.
- **Headless** (``--headless``): loop ``run_day`` N times and emit structured
  log lines. Used by QA scripts (spec §7.7), CI, and the manual QA artifacts.

The engine itself stays pure (no I/O, no clock). The headless runner is the
only place I/O happens — it wraps :func:`engine.tick.run_day` in an outer
loop and writes the autosave file at the boundary.

RNG pattern (CRITICAL): every ``run_day`` call seeds ``GameRNG`` with
``state.rng_seed + state.day`` — byte-identical to
``ui/app.py:140`` so the 3 frozen hashes (seed=42 day 100/1000/3650) survive.
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

# Strategy names are the 4 defaults from spec §3.1.
_VALID_STRATEGIES: tuple[str, ...] = ("aggressive", "conservative", "balanced", "genre_focus")


@dataclasses.dataclass(frozen=True, slots=True)
class CliArgs:
    """Parsed CLI arguments. Frozen + slotted for immutability."""

    seed: int
    ticks: int
    tick_rate: int
    headless: bool
    no_autosave: bool
    strategy: str | None
    dev: bool
    force_console_discontinue: int | None
    autosave_path: Path
    autosave_every: int


def parse_args(argv: list[str] | None = None) -> CliArgs:
    """Parse argv into a frozen CliArgs. Validates tick_rate in [1, 4]."""
    p = argparse.ArgumentParser(
        prog="htop-tycoon",
        description="htop-tycoon v3.0 — Game Dev Story TUI",
    )
    p.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    p.add_argument(
        "--ticks", type=int, default=0, help="Number of ticks in headless mode (default: 0)"
    )
    p.add_argument(
        "--tick-rate", type=int, default=1, help="Tick rate 1..4 in interactive mode (default: 1)"
    )
    p.add_argument("--headless", action="store_true", help="Run N ticks without TUI (QA mode)")
    p.add_argument("--no-autosave", action="store_true", help="Skip autosave writes")
    p.add_argument(
        "--strategy",
        type=str,
        default=None,
        choices=_VALID_STRATEGIES,
        help="Strategy to use in headless mode (default: manual / no strategy)",
    )
    p.add_argument("--dev", action="store_true", help="Developer mode (Korean log labels)")
    p.add_argument(
        "--force-console-discontinue",
        type=int,
        default=None,
        help="Force console discontinuation at this game-year (headless only)",
    )
    p.add_argument(
        "--autosave-path",
        type=Path,
        default=Path.home() / ".htop_tycoon_save.json",
        help="Autosave file path",
    )
    p.add_argument(
        "--autosave-every",
        type=int,
        default=100,
        help="Autosave cadence in ticks (default: 100)",
    )
    ns = p.parse_args(argv)

    if ns.tick_rate < 1 or ns.tick_rate > 4:
        p.error(f"--tick-rate must be in [1, 4], got {ns.tick_rate}")

    return CliArgs(
        seed=ns.seed,
        ticks=ns.ticks,
        tick_rate=ns.tick_rate,
        headless=ns.headless,
        no_autosave=ns.no_autosave,
        strategy=ns.strategy,
        dev=ns.dev,
        force_console_discontinue=ns.force_console_discontinue,
        autosave_path=ns.autosave_path,
        autosave_every=ns.autosave_every,
    )


def run_headless(args: CliArgs) -> int:
    """Run ``args.ticks`` ticks via ``run_day`` and log progress.

    Returns 0 on success. RNG pattern is byte-identical to ``ui/app.py:140``
    so the 3 frozen state hashes (seed=42 day 100/1000/3650) are preserved.
    """
    # Imported lazily so the CLI parser itself stays side-effect-free.
    from htop_tycoon.domain import GameState
    from htop_tycoon.engine.rng import GameRNG
    from htop_tycoon.engine.tick import run_day
    from htop_tycoon.persistence import save_state

    state = GameState(rng_seed=args.seed)

    # --strategy: resolve and register the default strategies.
    strategy = None
    if args.strategy is not None:
        from htop_tycoon.engine.strategy import get_strategy, register_default_strategies

        register_default_strategies()
        strategy = get_strategy(args.strategy)

    # --force-console-discontinue: walk state.market, patch licensed consoles.
    if args.force_console_discontinue is not None:
        new_consoles = []
        for cm in state.market.consoles:
            if cm.requires_license and cm.discontinue_year is None:
                new_consoles.append(
                    dataclasses.replace(cm, discontinue_year=args.force_console_discontinue)
                )
            else:
                new_consoles.append(cm)
        new_market = dataclasses.replace(state.market, consoles=tuple(new_consoles))
        state = state.replace(market=new_market)

    print(
        f"# htop-tycoon headless run seed={args.seed} ticks={args.ticks} "
        f"strategy={args.strategy or 'manual'}"
    )
    if args.force_console_discontinue is not None:
        print(f"# force_console_discontinue=year_{args.force_console_discontinue}")

    # Log ~20 evenly spaced lines max.
    log_interval = max(1, args.ticks // 20) if args.ticks > 0 else 1

    autosave_writes = 0
    for i in range(args.ticks):
        rng = GameRNG(state.rng_seed + state.day)  # MIRROR ui/app.py:140
        state, _events = run_day(state, rng, strategy=strategy)

        if (i + 1) % log_interval == 0:
            active = sum(1 for p in state.projects if not p.is_complete)
            print(
                f"day={state.day} cash={state.cash} fans={state.fans} "
                f"employees={len(state.employees)} active_projects={active}"
            )

        if (
            not args.no_autosave
            and args.autosave_every > 0
            and (i + 1) % args.autosave_every == 0
        ):
            save_state(args.autosave_path, state)
            autosave_writes += 1

        if state.ending is not None:
            print(f"# game ended day={state.day} ending={state.ending.kind.name}")
            break

    ending_name = state.ending.kind.name if state.ending else "NONE"
    print(
        f"# final day={state.day} cash={state.cash} fans={state.fans} "
        f"ending={ending_name} autosave_writes={autosave_writes}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    args = parse_args(argv)
    if args.headless:
        return run_headless(args)

    # Interactive TUI mode.
    from htop_tycoon.domain import GameState
    from htop_tycoon.ui import HtopTycoonApp

    HtopTycoonApp(state=GameState(rng_seed=args.seed), speed=args.tick_rate).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
