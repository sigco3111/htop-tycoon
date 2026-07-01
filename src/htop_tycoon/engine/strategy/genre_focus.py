"""htop-tycoon v3.0 — Genre Focus Strategy. Spec §3.1 row 4.

Spec §3.1 decision table row 4 (Genre Focus):
    - Auto-hire: Yes (within budget)
    - Auto-fire: No
    - Training: Focused on chosen genre
    - Game starts: Continuously
    - Genre choice: Spam chosen genre for combo bonuses
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from htop_tycoon.domain import Department, GameState, JobType, Platform
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.strategy.base import Strategy
from htop_tycoon.engine.strategy.types import PlannedAction

if TYPE_CHECKING:
    pass


# Spec §3.1: "Spam chosen genre for combo bonuses". The "chosen genre" is
# configured at construction; default = "action" (high-risk-high-reward).
_DEFAULT_GENRE: str = "action"
_DEFAULT_THEME: str = "stealth"  # 2.0x combo (spec §2.7)


class GenreFocusStrategy(Strategy):
    """Spec §3.1 row 4: spam one genre to chain combo bonuses.

    Constructor takes ``genre_id`` and ``theme_id`` so the player can pick
    which combo to farm. Default ``(action, stealth)`` is the spec's
    2.0x high-risk-high-reward pair.
    """

    name = "genre_focus"

    def __init__(
        self, genre_id: str = _DEFAULT_GENRE, theme_id: str = _DEFAULT_THEME
    ) -> None:
        self._genre_id = genre_id
        self._theme_id = theme_id

    def decide(
        self, state: GameState, rng: GameRNG
    ) -> list[PlannedAction]:
        actions: list[PlannedAction] = []

        # 1. Hire: yes, within budget (spec §3.1 — no cash threshold given,
        # so be conservative: only hire if cash > 30K to keep payroll sane).
        if state.cash > 30_000 and len(state.employees) < 8:
            actions.append(PlannedAction(
                kind="HIRE",
                target_id=None,
                params={
                    "dept": Department.PLANNING,
                    "job": JobType.GAME_DESIGNER,
                },
                priority=70,
            ))

        # 2. Start game: continuously (spec §3.1) — even if there's an
        # active project, queue another one. Engine will reject it with
        # the spec §3.2.1 "max 1 active project" guard, but the strategy
        # expresses intent.
        actions.append(PlannedAction(
            kind="START_GAME",
            target_id=None,
            params={
                "genre_id": self._genre_id,
                "theme_id": self._theme_id,
                "platform_id": Platform.PC.name,
            },
            priority=80,
        ))

        # 3. No fire (spec §3.1). No training logic (spec §3.1 only says
        # "focused on chosen genre" — generic training isn't genre-specific).
        return sorted(actions, key=lambda a: a.priority, reverse=True)


__all__ = ["GenreFocusStrategy"]
