"""htop-tycoon v3.0 — Ending dataclass. Spec §1.4."""
from __future__ import annotations

from dataclasses import dataclass

from htop_tycoon.domain.enums import EndingKind

__all__ = ["Ending"]


@dataclass(frozen=True, slots=True)
class Ending:
    """Captured state at end of game. Spec §1.4."""

    kind: EndingKind
    day: int
    cash_at_end: int
    games_count: int  # total released games (any platform)
    notes: str = ""  # free-form summary for UI

    @property
    def is_forced(self) -> bool:
        return self.kind.is_forced

    @property
    def is_soft(self) -> bool:
        return not self.is_forced

    @property
    def ko_label(self) -> str:
        return self.kind.ko_label
