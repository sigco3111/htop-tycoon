"""htop-tycoon v3.0 — Balanced Strategy. Spec §3.1 row 3.

Spec §3.1 decision table row 3 (Balanced):
    - Auto-hire: Yes (cash > 50K)
    - Auto-fire: Yes (very low performers — satisfaction < 0.10)
    - Training: Moderate
    - Game starts: If no project + cash > 20K
    - Genre choice: Mix of safe + occasional risk
"""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from htop_tycoon.domain import Department, GameState, JobType, Platform
from htop_tycoon.domain.ids import EntityId
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.strategy.base import Strategy
from htop_tycoon.engine.strategy.types import PlannedAction

if TYPE_CHECKING:
    pass


# Spec §3.1 thresholds (mirror balance.yaml::ai.balanced.*)
_HIRE_CASH_MIN: int = 50_000
_START_CASH_MIN: int = 20_000
_FIRE_SATISFACTION_MAX: float = 0.10


class BalancedStrategy(Strategy):
    """Spec §3.1 row 3: moderate mix of safe and risk decisions."""

    name = "balanced"

    def decide(
        self, state: GameState, rng: GameRNG
    ) -> list[PlannedAction]:
        actions: list[PlannedAction] = []

        # 1. Hire: cash > 50K and we have empty planning capacity
        if state.cash > _HIRE_CASH_MIN and len(state.employees) < 5:
            actions.append(PlannedAction(
                kind="HIRE",
                target_id=None,
                params={
                    "dept": Department.PLANNING,
                    "job": JobType.GAME_DESIGNER,
                },
                priority=70,
            ))

        # 2. Fire: very low satisfaction (Balanced auto-fires "very low" only)
        for emp in state.employees:
            if emp.satisfaction < _FIRE_SATISFACTION_MAX:
                actions.append(PlannedAction(
                    kind="FIRE",
                    target_id=cast(EntityId, emp.id),
                    params={"reason": "low_satisfaction"},
                    priority=60,
                ))
                break  # one fire per day

        # 3. Start game: no active project and cash > 20K
        if not state.active_projects() and state.cash > _START_CASH_MIN:
            actions.append(PlannedAction(
                kind="START_GAME",
                target_id=None,
                params={
                    "genre_id": "rpg",
                    "theme_id": "fantasy",
                    "platform_id": Platform.PC.name,
                },
                priority=80,
            ))

        return sorted(actions, key=lambda a: a.priority, reverse=True)


__all__ = ["BalancedStrategy"]
