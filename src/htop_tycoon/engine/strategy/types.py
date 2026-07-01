"""htop-tycoon v3.0 — PlannedAction schema. Spec §3.2.1.

The Strategy Manager (engine/strategy/) emits a list of ``PlannedAction``
records per game-day; the engine dispatch layer converts each into a
``dataclasses.replace`` on ``GameState`` plus an emitted ``Event``.

This is a separate ``ActionKind`` from ``domain.event.EventKind``:
- ``domain.event.EventKind`` — lowercase, the engine->UI event bus.
- ``engine.strategy.types.ActionKind`` — UPPERCASE, the strategy->engine
  intent bus. Spec §3.2.1 mandates the uppercase form.

Mapping from ``ActionKind`` to engine action is done in
``engine.strategy.dispatch``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from htop_tycoon.domain.ids import EntityId

ActionKind = Literal[
    "HIRE",          # params: {dept: Department, job: JobType}
    "FIRE",          # params: {employee_id: EmployeeId, reason: str}
    "TRAIN",         # params: {employee_id: EmployeeId, target_level: int}
    "START_GAME",    # params: {genre_id: str, theme_id: str, platform_id: str}
    "ASSIGN",        # params: {employee_id: EmployeeId, project_id: ProjectId}
    "PROMOTE",       # params: {employee_id: EmployeeId}
    "DEMOTE",        # params: {employee_id: EmployeeId}
    "CHANGE_JOB",    # params: {employee_id: EmployeeId, new_job: JobType}
    "NOTHING",       # no params; explicit "skip this day" marker
]


@dataclass(frozen=True, slots=True)
class PlannedAction:
    """A single AI decision. Spec §3.2.1.

    Strategies return a list sorted by ``priority`` desc. The engine
    dispatches the top-``MAX_ACTIONS_PER_DAY`` items per game-day.
    """
    kind: ActionKind
    target_id: EntityId | None = None
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 50  # 0..100; higher = earlier


__all__ = ["ActionKind", "PlannedAction"]
