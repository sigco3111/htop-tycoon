"""htop-tycoon v3.0 — Conservative Strategy. Spec §3.1 row 2.

Spec §3.1 decision table row 2 (Conservative):
    - Auto-hire: Only if cash > 100K
    - Auto-fire: Yes (low performers)
    - Training: Heavy before assign
    - Game starts: Only if cash > 50K
    - Genre choice: Safe, established combos
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


# Spec §3.1 thresholds (mirror balance.yaml::ai.conservative.*)
_HIRE_CASH_MIN: int = 100_000
_START_CASH_MIN: int = 50_000
_FIRE_SATISFACTION_MAX: float = 0.20  # waves out 0.10 vs balanced's "very low"
_TRAIN_LEVEL_TARGET: int = 2  # heavy training: train to L2 before assign


class ConservativeStrategy(Strategy):
    """Spec §3.1 row 2: only hire with high cash; fire low performers; safe genres."""

    name = "conservative"

    def decide(
        self, state: GameState, rng: GameRNG
    ) -> list[PlannedAction]:
        actions: list[PlannedAction] = []

        # 1. Fire: low performers (more aggressive threshold than balanced)
        for emp in state.employees:
            if emp.satisfaction < _FIRE_SATISFACTION_MAX:
                actions.append(PlannedAction(
                    kind="FIRE",
                    target_id=cast(EntityId, emp.id),
                    params={"reason": "low_satisfaction"},
                    priority=70,
                ))
                break  # one fire per day

        # 2. Hire: only if cash > 100K (very high threshold)
        if state.cash > _HIRE_CASH_MIN and len(state.employees) < 6:
            actions.append(PlannedAction(
                kind="HIRE",
                target_id=None,
                params={
                    "dept": Department.PLANNING,
                    "job": JobType.GAME_DESIGNER,
                },
                priority=60,
            ))

        # 3. Heavy training: train any low-level employees before assign
        for emp in state.employees:
            if emp.level < _TRAIN_LEVEL_TARGET and state.cash > 5_000:
                actions.append(PlannedAction(
                    kind="TRAIN",
                    target_id=cast(EntityId, emp.id),
                    params={"target_level": _TRAIN_LEVEL_TARGET},
                    priority=50,
                ))
                break  # one train per day

        # 4. Start game: only if cash > 50K (high threshold)
        if not state.active_projects() and state.cash > _START_CASH_MIN:
            actions.append(PlannedAction(
                kind="START_GAME",
                target_id=None,
                params={
                    # Safe, established combo per spec §3.1.
                    "genre_id": "simulation",
                    "theme_id": "modern",  # → 1.3x combo (편의점 시뮬)
                    "platform_id": Platform.PC.name,
                },
                priority=80,
            ))

        return sorted(actions, key=lambda a: a.priority, reverse=True)


__all__ = ["ConservativeStrategy"]
