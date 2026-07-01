"""htop-tycoon v3.0 — per-Console market state. Spec §2.3, §2.6."""
from __future__ import annotations

from dataclasses import dataclass

from htop_tycoon.domain.ids import ConsoleId

__all__ = ["ConsoleMarket"]


@dataclass(frozen=True, slots=True)
class ConsoleMarket:
    """Live state of a console's lifecycle curve and current popularity."""

    id: ConsoleId
    name_ko: str  # 디버그 / UI 표시용 — 정적 config에서 load됨
    base_popularity: float  # specs §2.8 lifecycle peak
    release_year: int  # 1-based year
    peak_year: int  # year of peak popularity
    decline_rate: float  # per-year multiplicative decay after peak
    discontinue_year: int | None  # None = permanent (PC, OWN_CONSOLE)
    royalty_rate: float  # 0..1; 0 for PC/own, 0.15 for licensed
    requires_license: bool
    current_popularity: float = 1.0  # populated at runtime
    day_since_release: int = 0  # tracks lifecycle position
    declined_at_day: int | None = None  # when popularity hit 0
    is_licensed: bool = False  # player paid license?

    @property
    def is_alive(self) -> bool:
        return self.current_popularity > 0.0

    @property
    def is_discontinued(self) -> bool:
        return self.declined_at_day is not None
