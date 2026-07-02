"""Meta-strategy selector — picks the optimal StrategyKind for current state.

Pure function. Deterministic given (state, rng). Used by auto_execute to
re-evaluate strategy every tick when state.auto_on is True.

Priority cascade (highest priority wins):
1. cash < 0 OR (cash < $20k AND any zombie exists) → CONSERVATIVE
2. cash >= $100k AND len(employees) < 5 → AGGRESSIVE
3. focus_genre set AND no in-progress focus project → GENRE_FOCUS
4. cash >= $100k AND len(employees) >= 7 → GENRE_FOCUS (depth pays off)
5. Otherwise → BALANCED
"""

from __future__ import annotations

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.domain.state import CompanyState

CASH_RICH_CENTS: int = 100_000_00
CASH_LOW_CENTS: int = 20_000_00
CASH_DEAD_CENTS: int = 0
HEADCOUNT_AGGRESSIVE_TARGET: int = 5
HEADCOUNT_GENRE_FOCUS_BONUS: int = 7


def pick_strategy(state: CompanyState, rng: GameRng) -> StrategyKind:
    """Pick the optimal StrategyKind for the current state."""
    del rng  # reserved for future stochastic tie-breaking
    cash = state.cash.cents
    employees = len(state.employees)
    has_zombie = any(e.is_zombie for e in state.employees.values())

    if cash < CASH_DEAD_CENTS or (cash < CASH_LOW_CENTS and has_zombie):
        return StrategyKind.CONSERVATIVE
    if cash >= CASH_RICH_CENTS and employees < HEADCOUNT_AGGRESSIVE_TARGET:
        return StrategyKind.AGGRESSIVE
    if state.focus_genre is not None:
        in_progress_focus = [
            p for p in state.projects.values()
            if p.genre == state.focus_genre and p.progress.value < 100
        ]
        if not in_progress_focus:
            return StrategyKind.GENRE_FOCUS
    if cash >= CASH_RICH_CENTS and employees >= HEADCOUNT_GENRE_FOCUS_BONUS:
        return StrategyKind.GENRE_FOCUS
    return StrategyKind.BALANCED