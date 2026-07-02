"""EventLogPanel — body widget showing recent strategy decisions + state events.

Phase 2L. Renders the last N events from state.event_log with kind +
day_index + description. Pure renderer (no state mutation).
"""

from __future__ import annotations

from htop_tycoon.domain import CompanyState
from htop_tycoon.engine.event_log import Event

MAX_VISIBLE_EVENTS: int = 5


class EventLogPanel:
    """Body widget that renders the most recent strategy / state events.

    Reads state.event_log; renders up to MAX_VISIBLE_EVENTS most recent
    events. Pure — no side effects.
    """

    __slots__ = ("_state",)

    def __init__(self, state: CompanyState) -> None:
        self._state = state

    def render(self) -> str:
        events: list[Event] = [
            e for e in self._state.event_log if isinstance(e, Event)
        ]
        if not events:
            return "Event Log (no events yet — wait for strategy to fire)"
        recent = events[-MAX_VISIBLE_EVENTS:]
        lines = [f"Event Log (last {len(recent)} of {len(events)})"]
        for e in recent:
            lines.append(
                f"  Y{e.year}D{e.day_index:<3} {e.kind.value:<18} {e.description[:60]}"
            )
        return "\n".join(lines)
