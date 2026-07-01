"""htop-tycoon v3.0 — Event bus payload. Spec §5.3 (engine → UI one-way)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

__all__ = ["Event", "EventKind"]

EventKind = Literal[
    "tick", "hire", "fire", "train", "start_game", "assign",
    "promote", "demote", "change_job", "sales", "award", "milestone",
    "fan_decay", "console_discontinue", "ending",
]


@dataclass(frozen=True, slots=True)
class Event:
    """Engine emits events; UI consumes them. Spec §5.3."""

    kind: EventKind  # EventKind is a Literal — assignable from any of those strings
    day: int
    payload: Mapping[str, Any] | None = None
    priority: int = 0  # higher = rendered earlier in UI lists

    def __post_init__(self) -> None:
        if self.payload is not None:
            object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
