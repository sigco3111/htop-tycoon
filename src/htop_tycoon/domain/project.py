"""GameProject entity — a game in development or shipped.

Frozen dataclass with methods returning new instances for any "mutation".
team_ids is normalized to a tuple in __post_init__ so hashability and
frozen semantics are preserved.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from htop_tycoon.domain.enums import Console, Genre, Platform
from htop_tycoon.domain.ids import EmployeeId, GameTitle, ProjectId
from htop_tycoon.domain.quality import Progress, QualityAxes


@dataclass(frozen=True, slots=True)
class GameProject:
    id: ProjectId
    title: GameTitle
    genre: Genre
    platform: Platform
    console: Console | None
    progress: Progress
    quality: QualityAxes
    days_in_dev: int
    lead_id: EmployeeId | None
    team_ids: tuple[EmployeeId, ...] = field(default=())
    units_sold: int = 0
    hall_of_fame: bool = False

    def __post_init__(self) -> None:
        # Normalize team_ids to tuple — preserves frozen + hashable semantics.
        if not isinstance(self.team_ids, tuple):
            object.__setattr__(self, "team_ids", tuple(self.team_ids))
        if self.days_in_dev < 0:
            raise ValueError(f"days_in_dev must be >= 0, got {self.days_in_dev}")
        if self.platform == Platform.CONSOLE and self.console is None:
            raise ValueError(
                "platform=CONSOLE requires a non-None console (e.g. NOVA, GENESIS_X)"
            )

    @property
    def is_shipped(self) -> bool:
        return self.progress.is_complete

    def advance(self, delta: int) -> GameProject:
        return GameProject(
            id=self.id,
            title=self.title,
            genre=self.genre,
            platform=self.platform,
            console=self.console,
            progress=self.progress.with_increment(delta),
            quality=self.quality,
            days_in_dev=self.days_in_dev + 1,
            lead_id=self.lead_id,
            team_ids=self.team_ids,
        )

    def assign_lead(self, lead_id: EmployeeId) -> GameProject:
        return GameProject(
            id=self.id,
            title=self.title,
            genre=self.genre,
            platform=self.platform,
            console=self.console,
            progress=self.progress,
            quality=self.quality,
            days_in_dev=self.days_in_dev,
            lead_id=lead_id,
            team_ids=self.team_ids,
        )

    def add_team_member(self, employee_id: EmployeeId) -> GameProject:
        if employee_id in self.team_ids:
            return self
        new_team: tuple[EmployeeId, ...] = (*self.team_ids, employee_id)
        return GameProject(
            id=self.id,
            title=self.title,
            genre=self.genre,
            platform=self.platform,
            console=self.console,
            progress=self.progress,
            quality=self.quality,
            days_in_dev=self.days_in_dev,
            lead_id=self.lead_id,
            team_ids=new_team,
        )


def _coerce_team_ids(value: Iterable[EmployeeId]) -> tuple[EmployeeId, ...]:
    return tuple(value)
