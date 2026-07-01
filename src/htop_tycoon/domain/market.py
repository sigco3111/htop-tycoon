"""htop-tycoon v3.0 — top-level Market state. Spec §2.6."""
from __future__ import annotations

from dataclasses import dataclass, field

from htop_tycoon.domain.console_market import ConsoleMarket
from htop_tycoon.domain.ids import ConsoleId

__all__ = ["Market"]


@dataclass(frozen=True, slots=True)
class Market:
    """Company-wide market view; holds per-console state."""

    consoles: tuple[ConsoleMarket, ...] = field(default_factory=tuple)
    last_decay_day: int = 0  # spec §2.6: decay every 90 game-days

    def consoles_alive(self) -> tuple[ConsoleMarket, ...]:
        return tuple(c for c in self.consoles if c.is_alive)

    def by_id(self, console_id: ConsoleId) -> ConsoleMarket:
        for c in self.consoles:
            if c.id == console_id:
                return c
        raise KeyError(f"console not found: {console_id}")
