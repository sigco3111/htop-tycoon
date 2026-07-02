"""Engine layer: pure logic that advances CompanyState day-by-day.

Phase 2B module. No UI imports, no module-level random access — all
randomness flows through GameRng passed in by callers.
"""

from htop_tycoon.engine.game_dev import (
    BASE_PROGRESS_PER_DAY,
    GENRE_FACTOR,
    TEAM_SIZE_BONUS_CAP,
    advance_projects,
    compute_daily_progress,
)
from htop_tycoon.engine.market import (
    CONSOLE_POPULARITY,
    DEFAULT_TREND,
    PLATFORM_POPULARITY,
    MarketState,
)
from htop_tycoon.engine.productivity import (
    JITTER_DIVISOR,
    JITTER_MAX,
    JITTER_MIN,
    JOB_TIER,
    MAX_LEVEL,
    MAX_TIER,
    compute_employee_productivity,
)
from htop_tycoon.engine.sales import (
    BASE_UNITS_SOLD,
    PLATFORM_PRICE_CENTS,
    QUALITY_MAX_SUM,
    compute_sales_revenue,
)
from htop_tycoon.engine.tick import (
    DEFAULT_MARKET,
    FANS_PER_SHIPMENT_UNIT,
    SATISFACTION_MAX,
    SATISFACTION_MIN,
    tick,
)

__all__ = [
    "MarketState",
    "PLATFORM_POPULARITY",
    "CONSOLE_POPULARITY",
    "DEFAULT_TREND",
    "compute_employee_productivity",
    "JOB_TIER",
    "MAX_LEVEL",
    "MAX_TIER",
    "JITTER_MIN",
    "JITTER_MAX",
    "JITTER_DIVISOR",
    "compute_daily_progress",
    "advance_projects",
    "BASE_PROGRESS_PER_DAY",
    "TEAM_SIZE_BONUS_CAP",
    "GENRE_FACTOR",
    "compute_sales_revenue",
    "BASE_UNITS_SOLD",
    "PLATFORM_PRICE_CENTS",
    "QUALITY_MAX_SUM",
    "tick",
    "DEFAULT_MARKET",
    "FANS_PER_SHIPMENT_UNIT",
    "SATISFACTION_MIN",
    "SATISFACTION_MAX",
]
