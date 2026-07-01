"""htop-tycoon v3.0 — deterministic engine layer. Spec §5.3.

Public API:

  Per-day simulation:
    - run_day(state, rng) -> (GameState, list[Event])
        Top-level driver used by both the manual TUI loop and the Strategy
        Manager (Wave 4+). Spec §5.2.

  Pure actions (spec §3.2.1, 9 of them):
    - hire, fire, train, promote, demote, change_job,
      start_game, assign, nothing

All modules under this package are pure: no I/O, no clock access, no bare
``random.*`` calls. The only randomness gateway is ``engine.rng.GameRNG``.
"""
from htop_tycoon.engine.actions import (
    CONSOLE_LICENSE_FEE,
    FIRE_SEVERANCE,
    HIRE_COST,
    JOB_CHANGE_MULTIPLIER,
    MAX_ACTIONS_PER_DAY,
    MAX_LEVEL,
    TRAIN_COST_PER_LEVEL,
    assign,
    change_job,
    demote,
    fire,
    hire,
    nothing,
    promote,
    start_game,
    train,
)
from htop_tycoon.engine.award import run_game_show, run_year_end_ceremony
from htop_tycoon.engine.endings import check_endings
from htop_tycoon.engine.market import tick_market
from htop_tycoon.engine.rng import CORRUPTION_RECOVERY_SEED, GameRNG
from htop_tycoon.engine.sales import (
    FANS_PER_COPY,
    compute_sales,
    fans_gained_from_sales,
    get_combo_multiplier,
)
from htop_tycoon.engine.tick import run_day

__all__ = [
    "CONSOLE_LICENSE_FEE",
    "CORRUPTION_RECOVERY_SEED",
    "FANS_PER_COPY",
    "FIRE_SEVERANCE",
    "GameRNG",
    "HIRE_COST",
    "JOB_CHANGE_MULTIPLIER",
    "MAX_ACTIONS_PER_DAY",
    "MAX_LEVEL",
    "TRAIN_COST_PER_LEVEL",
    "assign",
    "change_job",
    "check_endings",
    "compute_sales",
    "demote",
    "fans_gained_from_sales",
    "fire",
    "get_combo_multiplier",
    "hire",
    "nothing",
    "promote",
    "run_day",
    "run_game_show",
    "run_year_end_ceremony",
    "start_game",
    "tick_market",
    "train",
]
