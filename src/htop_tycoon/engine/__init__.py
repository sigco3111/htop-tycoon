"""htop-tycoon v3.0 — deterministic engine layer. Spec §5.3.

Public API:

  Per-day simulation (spec §5.2):
    - run_day(state, rng, strategy=None) -> (GameState, list[Event])
        Top-level driver. Pass ``strategy`` to enable AI auto-play (Wave 4+);
        ``None`` means manual play (the UI dispatches actions directly).

  Pure actions (spec §3.2.1, 9 of them):
    - hire, fire, train, promote, demote, change_job,
      start_game, assign, nothing

  Sales (spec §2.2 step 8 + §2.6):
    - compute_sales(state, project, console) -> (gross, net)
    - get_combo_multiplier(genre, theme) -> float
    - fans_gained_from_sales(copies) -> int

  Strategy Manager (spec §3.2 + §3.3):
    - BalancedStrategy, AggressiveStrategy, ConservativeStrategy, GenreFocusStrategy
    - StrategyRegistry / register_default_strategies() / get_strategy(name)
    - dispatch_action(state, rng, action) -> (state, events)

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
from htop_tycoon.engine.strategy import (
    AggressiveStrategy,
    BalancedStrategy,
    ConservativeStrategy,
    GenreFocusStrategy,
    Strategy,
    StrategyRegistry,
    get_strategy,
    register_default_strategies,
)
from htop_tycoon.engine.tick import run_day

__all__ = [
    "AggressiveStrategy",
    "BalancedStrategy",
    "CONSOLE_LICENSE_FEE",
    "CORRUPTION_RECOVERY_SEED",
    "ConservativeStrategy",
    "FANS_PER_COPY",
    "FIRE_SEVERANCE",
    "GameRNG",
    "GenreFocusStrategy",
    "HIRE_COST",
    "JOB_CHANGE_MULTIPLIER",
    "MAX_ACTIONS_PER_DAY",
    "MAX_LEVEL",
    "Strategy",
    "StrategyRegistry",
    "TRAIN_COST_PER_LEVEL",
    "assign",
    "change_job",
    "check_endings",
    "compute_sales",
    "demote",
    "fans_gained_from_sales",
    "fire",
    "get_combo_multiplier",
    "get_strategy",
    "hire",
    "nothing",
    "promote",
    "register_default_strategies",
    "run_day",
    "run_game_show",
    "run_year_end_ceremony",
    "start_game",
    "tick_market",
    "train",
]

