"""Engine layer: pure logic that advances CompanyState day-by-day.

Phase 2B module. No UI imports, no module-level random access — all
randomness flows through GameRng passed in by callers.
"""

from htop_tycoon.engine.market import MarketState

__all__ = ["MarketState"]
