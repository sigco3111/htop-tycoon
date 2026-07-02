"""Strategy module: AI decision-making for the engine tick.

Phase 2H. Pure logic — no UI, no I/O. Strategies read CompanyState
and emit StrategyDecisions describing what the engine should do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    """Single decision emitted by a strategy for one tick.

    action: verb describing what to do (hire, fire, start_project, etc.)
    target: scope of the action (any, RPG, Lead, zombie, etc.)
    magnitude: numeric size hint (e.g., employees to hire)
    reason: human-readable explanation
    """

    action: str
    target: str
    magnitude: int
    reason: str
