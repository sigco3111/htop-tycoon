"""Event log — record of strategy decisions and state changes for review.

Phase 2K. Events are immutable frozen dataclasses; CompanyState.event_log
is a tuple. New events are appended via state.append_event().
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EventKind(StrEnum):
    HIRE = "hire"
    FIRE = "fire"
    START_PROJECT = "start_project"
    SAVE_CASH = "save_cash"
    BOOST_FUNDING = "boost_funding"
    INCREASE_FUNDING = "increase_funding"
    SHIP = "ship"
    BANKRUPTCY = "bankruptcy"
    VOLUNTARY_SALE = "voluntary_sale"
    MEGA_HIT = "mega_hit"
    PURCHASE_CONSOLE = "purchase_console"
    RELEASE = "release"
    STRATEGY_CHANGED = "strategy_changed"
    PROMOTE = "promote"


@dataclass(frozen=True, slots=True)
class Event:
    day_index: int
    year: int
    kind: EventKind
    description: str


__all__ = ["Event", "EventKind"]
