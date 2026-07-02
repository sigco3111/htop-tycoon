"""Strategy dispatch: STRATEGY_REGISTRY + current_strategy(state)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from htop_tycoon.engine.strategy.base import Strategy
from htop_tycoon.engine.strategy.strategies import (
    AggressiveStrategy,
    BalancedStrategy,
    ConservativeStrategy,
    GenreFocusStrategy,
)

if TYPE_CHECKING:
    from htop_tycoon.domain.state import CompanyState


STRATEGY_REGISTRY: dict[str, type[Strategy]] = {
    "AGGRESSIVE": AggressiveStrategy,
    "CONSERVATIVE": ConservativeStrategy,
    "BALANCED": BalancedStrategy,
    "GENRE_FOCUS": GenreFocusStrategy,
}


def current_strategy(state: CompanyState) -> Strategy:
    """Instantiate the strategy that matches state.strategy."""
    cls = STRATEGY_REGISTRY[state.strategy.value]
    if cls is GenreFocusStrategy:
        return cls(state.focus_genre)
    return cls()


__all__ = ["STRATEGY_REGISTRY", "current_strategy"]
