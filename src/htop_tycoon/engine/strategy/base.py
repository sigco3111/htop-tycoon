"""htop-tycoon v3.0 — Strategy ABC + Registry. Spec §3.2.2 + §3.2.3."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from htop_tycoon.domain import GameState
    from htop_tycoon.engine.rng import GameRNG
    from htop_tycoon.engine.strategy.types import PlannedAction


class Strategy(ABC):
    """Spec §3.2.2: common interface for the 4 strategies.

    Concrete strategies (aggressive / conservative / balanced / genre_focus)
    implement :meth:`decide` and may override :meth:`post_execute`. The
    registry is the lookup surface; see :class:`StrategyRegistry`.
    """

    name: str  # "aggressive" | "conservative" | "balanced" | "genre_focus"

    @abstractmethod
    def decide(
        self, state: GameState, rng: GameRNG
    ) -> list[PlannedAction]:
        """Return the day's planned actions, sorted by priority desc.

        Spec §6 caps the result at ``balance.ai.max_actions_per_day``
        (default 10). Concrete strategies may return up to that many.
        """

    def post_execute(
        self, state: GameState, executed: list[PlannedAction]
    ) -> None:
        """Optional hook called after actions are applied. Default: no-op.

        Spec §3.2.2: ``post_execute(self, state, executed) -> None``.
        """
        return None  # default no-op per spec §3.2.2


class StrategyRegistry:
    """Spec §3.2.3: registry of strategies by name (string key).

    Strategies are registered via :meth:`register` and looked up via
    :meth:`get`. The default Wave 3 strategies are registered by
    :func:`engine.strategy.register_default_strategies` (called from
    :mod:`engine.strategy.__init__`).
    """

    _registry: dict[str, type[Strategy]] = {}

    @classmethod
    def register(cls, name: str, strategy_cls: type[Strategy]) -> None:
        if name in cls._registry:
            raise ValueError(f"strategy already registered: {name!r}")
        cls._registry[name] = strategy_cls

    @classmethod
    def unregister(cls, name: str) -> None:
        cls._registry.pop(name, None)

    @classmethod
    def get(cls, name: str) -> Strategy:
        if name not in cls._registry:
            raise KeyError(
                f"strategy not registered: {name!r}. "
                f"Available: {sorted(cls._registry.keys())}"
            )
        return cls._registry[name]()

    @classmethod
    def names(cls) -> list[str]:
        return sorted(cls._registry.keys())


__all__ = ["Strategy", "StrategyRegistry"]
