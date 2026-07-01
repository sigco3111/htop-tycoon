"""htop-tycoon v3.0 — GameProject domain dataclass. Spec §2.2."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from htop_tycoon.domain.enums import QualityAxis
from htop_tycoon.domain.ids import (
    EmployeeId,
    GenreId,
    PlatformId,
    ProjectId,
    ThemeId,
)

__all__ = ["GameProject"]


@dataclass(frozen=True, slots=True)
class GameProject:
    """A game in development or post-launch. Spec §2.2 + §5.3."""

    id: ProjectId
    name: str  # Korean title; may include combo flavor (e.g., "시간여행 RPG")
    genre_id: GenreId
    theme_id: ThemeId
    # PRIMARY platform; cross-platform releases use a derived GameProject
    # per Platform in Wave 3+.
    platform_id: PlatformId
    progress_pct: float = 0.0  # 0..100; sales only after is_complete
    # 0..10 average per critic, exposed read-only via MappingProxyType.
    quality_axes: Mapping[QualityAxis, float] = field(default_factory=dict)
    assignees: tuple[EmployeeId, ...] = ()
    started_day: int = 1
    sales_total: int = 0
    fan_boost: float = 0.0  # 0..1; applied during game-show effect (spec §2.4)
    # None until progress hits 100 and a release action runs (Wave 3+).
    released_day: int | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.progress_pct <= 100.0:
            raise ValueError(f"progress_pct must be in 0..100; got {self.progress_pct}")
        if not 0.0 <= self.fan_boost <= 1.0:
            raise ValueError(f"fan_boost must be in 0..1; got {self.fan_boost}")
        if any(v < 0.0 or v > 10.0 for v in self.quality_axes.values()):
            raise ValueError("quality_axes values must be in 0..10 (spec §2.2 step 6)")
        # quality_axes must be immutable from outside
        object.__setattr__(self, "quality_axes", MappingProxyType(dict(self.quality_axes)))

    @property
    def is_complete(self) -> bool:
        return self.progress_pct >= 100.0

    @property
    def is_released(self) -> bool:
        return self.released_day is not None

    @property
    def current_quality_avg(self) -> float:
        if not self.quality_axes:
            return 0.0
        return sum(self.quality_axes.values()) / len(self.quality_axes)
