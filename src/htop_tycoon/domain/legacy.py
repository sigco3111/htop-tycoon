"""htop-tycoon v3.0 — Legacy Score (achievements tracker). Spec §1.5."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TypeAlias

JSONScalar: TypeAlias = str | int | float | bool | None
"""JSON-native scalar union — avoids Any leakage (AGENTS.md §8)."""

__all__ = ["AchievementUnlock", "JSONScalar", "LegacyScore"]


@dataclass(frozen=True, slots=True)
class AchievementUnlock:
    """One achievement on a player's legacy record. Spec §1.5."""

    id: str
    name_ko: str
    unlocked_day: int
    context: Mapping[str, JSONScalar] | None = None  # structured per data/achievements.yaml

    def __post_init__(self) -> None:
        if self.context is not None:
            object.__setattr__(self, "context", MappingProxyType(dict(self.context)))


@dataclass(frozen=True, slots=True)
class LegacyScore:
    """Player's persistent achievement record (does NOT reset on Bankruptcy). Spec §1.5.

    Frozen; modify via `.unlock(...)` which returns a new LegacyScore with
    the new achievement appended (no duplicates by id).
    """

    achievements: tuple[AchievementUnlock, ...] = field(default_factory=tuple)
    points: int = 0  # accumulated score; default 0

    def unlock(self, unlock: AchievementUnlock) -> LegacyScore:
        """Append an achievement; dedup by id; returns new LegacyScore."""
        if any(a.id == unlock.id for a in self.achievements):
            return self  # already unlocked
        # Caller decides how many points this achievement is worth — for now 100.
        new_achievements = self.achievements + (unlock,)
        return replace(self, achievements=new_achievements, points=self.points + 100)

    def has(self, achievement_id: str) -> bool:
        return any(a.id == achievement_id for a in self.achievements)
