"""sales — compute revenue from shipping a project."""

from __future__ import annotations

from htop_tycoon.domain.enums import Platform
from htop_tycoon.domain.money import Money
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine.game_dev import GENRE_FACTOR
from htop_tycoon.engine.market import MarketState

BASE_UNITS_SOLD: int = 10_000

PLATFORM_PRICE_CENTS: dict[Platform, int] = {
    Platform.PC: 3000,
    Platform.MOBILE: 500,
    Platform.CONSOLE: 4000,
    Platform.HANDHELD: 2500,
}

QUALITY_MAX_SUM: int = 400
JITTER_MIN: int = 90
JITTER_MAX: int = 110
JITTER_DIVISOR: int = 100


def compute_sales_revenue(
    project: GameProject, market: MarketState, rng: GameRng
) -> Money:
    """Revenue from one shipment event.

    Formula: base_units × popularity × (quality_sum/400) × trend × genre × jitter × price/unit.
    """
    price_cents = PLATFORM_PRICE_CENTS[project.platform]
    quality_factor = project.quality.sum() / QUALITY_MAX_SUM
    genre_factor = GENRE_FACTOR[project.genre]
    jitter = rng.int_range(JITTER_MIN, JITTER_MAX) / JITTER_DIVISOR
    units_sold = (
        BASE_UNITS_SOLD
        * market.popularity
        * quality_factor
        * genre_factor
        * market.trend
        * jitter
    )
    revenue_cents = int(units_sold * price_cents)
    return Money(revenue_cents)
