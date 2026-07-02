"""Strategy ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from htop_tycoon.domain.rng import GameRng
    from htop_tycoon.domain.state import CompanyState
    from htop_tycoon.engine.strategy.types import StrategyDecision


class Strategy(ABC):
    """Abstract base for AI strategies. Pure logic — no state mutation."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def decide(
        self, state: CompanyState, rng: GameRng
    ) -> list[StrategyDecision]: ...


__all__ = ["Strategy"]
