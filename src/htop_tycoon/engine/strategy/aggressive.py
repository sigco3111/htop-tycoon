"""htop-tycoon v3.0 — Aggressive Strategy. Spec §3.1 row 1.

Spec §3.1 decision table row 1 (Aggressive):
    - Auto-hire: Yes (cash > 30K)
    - Auto-fire: No (keep all)
    - Training: Minimal
    - Game starts: Immediately if no active project
    - Genre choice: High-risk high-reward combos
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from htop_tycoon.domain import Department, GameState, JobType, Platform
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.strategy.base import Strategy
from htop_tycoon.engine.strategy.types import PlannedAction

if TYPE_CHECKING:
    pass


# Spec §3.1 thresholds (mirror balance.yaml::ai.aggression.*)
_HIRE_CASH_MIN: int = 30_000


class AggressiveStrategy(Strategy):
    """Spec §3.1 row 1: high-risk, high-reward. Never fires, hires freely."""

    name = "aggressive"

    def decide(
        self, state: GameState, rng: GameRNG
    ) -> list[PlannedAction]:
        actions: list[PlannedAction] = []

        # Aggressive never fires employees (spec §3.1).
        # 1. Hire: cash > 30K (lower threshold than Balanced)
        if state.cash > _HIRE_CASH_MIN:
            actions.append(PlannedAction(
                kind="HIRE",
                target_id=None,
                params={
                    "dept": Department.PLANNING,
                    "job": JobType.GAME_DESIGNER,
                },
                priority=70,
            ))

        # 2. Start game: immediately if no active project (spec §3.1).
        if not state.active_projects():
            actions.append(PlannedAction(
                kind="START_GAME",
                target_id=None,
                params={
                    # High-risk high-reward per spec §3.1.
                    "genre_id": "action",
                    "theme_id": "stealth",  # → 2.0x combo (spec §2.7 닌자 액션)
                    "platform_id": Platform.PC.name,
                },
                priority=90,
            ))

        return sorted(actions, key=lambda a: a.priority, reverse=True)


__all__ = ["AggressiveStrategy"]
