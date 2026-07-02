"""Strategy ABC + 4 concrete strategies + dispatch registry + meta-strategy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from htop_tycoon.domain.enums import Genre
from htop_tycoon.engine.strategy.meta_strategy import (
    CASH_DEAD_CENTS,
    CASH_LOW_CENTS,
    CASH_RICH_CENTS,
    HEADCOUNT_AGGRESSIVE_TARGET,
    HEADCOUNT_GENRE_FOCUS_BONUS,
    pick_strategy,
)
from htop_tycoon.engine.strategy.types import StrategyDecision

if TYPE_CHECKING:
    from htop_tycoon.domain.rng import GameRng
    from htop_tycoon.domain.state import CompanyState


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


class AggressiveStrategy(Strategy):
    """Hire fast, start big projects, take risks."""

    HIRE_CASH_THRESHOLD_CENTS: int = 50_000_00
    HIRE_TARGET_HEADCOUNT: int = 8
    HIRE_BATCH: int = 2
    START_PROJECT_CASH_THRESHOLD_CENTS: int = 30_000_00
    LOW_QUALITY_THRESHOLD: int = 200

    @property
    def name(self) -> str:
        return "Aggressive"

    @property
    def description(self) -> str:
        return "Hire fast, big projects, take risks"

    def decide(
        self, state: CompanyState, rng: GameRng
    ) -> list[StrategyDecision]:
        decisions: list[StrategyDecision] = []
        if (
            state.cash.cents >= self.HIRE_CASH_THRESHOLD_CENTS
            and len(state.employees) < self.HIRE_TARGET_HEADCOUNT
        ):
            decisions.append(
                StrategyDecision(
                    action="hire",
                    target="any",
                    magnitude=self.HIRE_BATCH,
                    reason="aggressive growth",
                )
            )
        if (
            len(state.projects) == 0
            and state.cash.cents >= self.START_PROJECT_CASH_THRESHOLD_CENTS
        ):
            decisions.append(
                StrategyDecision(
                    action="start_project",
                    target="RPG",
                    magnitude=1,
                    reason="no active project",
                )
            )
        avg_quality = (
            sum(p.quality.sum() for p in state.projects.values())
            / max(1, len(state.projects))
        )
        if state.projects and avg_quality < self.LOW_QUALITY_THRESHOLD:
            decisions.append(
                StrategyDecision(
                    action="increase_funding",
                    target="any",
                    magnitude=int(state.cash.cents * 0.10),
                    reason="low quality across projects",
                )
            )
        return decisions


class ConservativeStrategy(Strategy):
    """Slow & steady; cut losses when cash is low."""

    HIRE_CASH_THRESHOLD_CENTS: int = 80_000_00
    FIRE_CASH_THRESHOLD_CENTS: int = 20_000_00
    SAVE_CASH_THRESHOLD_CENTS: int = 30_000_00

    @property
    def name(self) -> str:
        return "Conservative"

    @property
    def description(self) -> str:
        return "Slow & steady; cut losses when cash is low"

    def decide(
        self, state: CompanyState, rng: GameRng
    ) -> list[StrategyDecision]:
        decisions: list[StrategyDecision] = []
        if state.cash.cents >= self.HIRE_CASH_THRESHOLD_CENTS:
            decisions.append(
                StrategyDecision(
                    action="hire",
                    target="any",
                    magnitude=1,
                    reason="cash buffer allows 1 hire",
                )
            )
        if state.cash.cents < self.FIRE_CASH_THRESHOLD_CENTS:
            zombies = [e for e in state.employees.values() if e.is_zombie]
            if zombies:
                decisions.append(
                    StrategyDecision(
                        action="fire",
                        target="zombie",
                        magnitude=1,
                        reason="low cash — shed weakest",
                    )
                )
        if state.cash.cents >= self.SAVE_CASH_THRESHOLD_CENTS:
            decisions.append(
                StrategyDecision(
                    action="save_cash",
                    target="any",
                    magnitude=0,
                    reason="preserve liquidity",
                )
            )
        return decisions


class BalancedStrategy(Strategy):
    """Mix of all — moderate hiring, project starts based on cash."""

    HIRE_HEADCOUNT_TARGET: int = 5
    START_PROJECT_CASH_THRESHOLD_CENTS: int = 50_000_00
    GENRE_CHOICES: tuple[str, ...] = (
        "ACTION", "RPG", "ADVENTURE", "SIMULATION", "PUZZLE", "STRATEGY",
        "SPORTS", "HORROR", "CASUAL",
    )

    @property
    def name(self) -> str:
        return "Balanced"

    @property
    def description(self) -> str:
        return "Moderate hiring, mixed project sizes"

    def decide(
        self, state: CompanyState, rng: GameRng
    ) -> list[StrategyDecision]:
        decisions: list[StrategyDecision] = []
        if len(state.employees) < self.HIRE_HEADCOUNT_TARGET:
            decisions.append(
                StrategyDecision(
                    action="hire",
                    target="any",
                    magnitude=1,
                    reason="understaffed",
                )
            )
        if (
            state.cash.cents >= self.START_PROJECT_CASH_THRESHOLD_CENTS
            and len(state.projects) == 0
        ):
            chosen_genre = rng.choice(self.GENRE_CHOICES)
            decisions.append(
                StrategyDecision(
                    action="start_project",
                    target=chosen_genre,
                    magnitude=1,
                    reason="no active project",
                )
            )
        return decisions


class GenreFocusStrategy(Strategy):
    """Concentrate resources on a single genre."""

    DEFAULT_FOCUS: str = "RPG"
    BOOST_PROGRESS_THRESHOLD: int = 50
    BOOST_MAGNITUDE: int = 5

    def __init__(self, focus_genre: Genre | None = None) -> None:
        self._focus_genre = focus_genre

    @property
    def focus_genre(self) -> Genre:
        return self._focus_genre if self._focus_genre is not None else Genre.RPG

    @property
    def name(self) -> str:
        return "Genre Focus"

    @property
    def description(self) -> str:
        return f"Concentrate resources on {self.focus_genre.value}"

    def decide(
        self, state: CompanyState, rng: GameRng
    ) -> list[StrategyDecision]:
        decisions: list[StrategyDecision] = []
        focus = state.focus_genre if state.focus_genre is not None else self.focus_genre
        in_progress_focus = [
            p for p in state.projects.values()
            if p.genre == focus and p.progress.value < 100
        ]
        if not in_progress_focus:
            decisions.append(
                StrategyDecision(
                    action="start_project",
                    target=focus.value,
                    magnitude=1,
                    reason="focus genre has no active project",
                )
            )
            return decisions
        if any(p.progress.value < self.BOOST_PROGRESS_THRESHOLD for p in in_progress_focus):
            decisions.append(
                StrategyDecision(
                    action="boost_funding",
                    target=focus.value,
                    magnitude=self.BOOST_MAGNITUDE,
                    reason="boost under-50% focus project",
                )
            )
        return decisions


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


__all__ = [
    "CASH_DEAD_CENTS",
    "CASH_LOW_CENTS",
    "CASH_RICH_CENTS",
    "HEADCOUNT_AGGRESSIVE_TARGET",
    "HEADCOUNT_GENRE_FOCUS_BONUS",
    "STRATEGY_REGISTRY",
    "AggressiveStrategy",
    "BalancedStrategy",
    "ConservativeStrategy",
    "GenreFocusStrategy",
    "Strategy",
    "current_strategy",
    "pick_strategy",
]
