"""EventLogPanel — body widget showing recent strategy decisions + state events."""

from __future__ import annotations

from htop_tycoon.domain import CompanyState
from htop_tycoon.engine.event_log import Event
from htop_tycoon.ui.i18n import EVENT_KIND_KO

MAX_VISIBLE_EVENTS: int = 5


class EventLogPanel:
    """Body widget that renders the most recent strategy / state events."""

    __slots__ = ("_state",)

    def __init__(self, state: CompanyState) -> None:
        self._state = state

    def render(self) -> str:
        events: list[Event] = [
            e for e in self._state.event_log if isinstance(e, Event)
        ]
        if not events:
            return "이벤트 로그 (아직 이벤트 없음 — 전략이 실행될 때까지 기다리세요)"
        recent = events[-MAX_VISIBLE_EVENTS:]
        lines = [f"이벤트 로그 (최근 {len(recent)}건 / 전체 {len(events)}건)"]
        for e in recent:
            kind_ko = EVENT_KIND_KO.get(e.kind.value, e.kind.value)
            lines.append(
                f"  {e.year}년 {e.day_index:>3}일 {kind_ko:<10} {e.description[:60]}"
            )
        return "\n".join(lines)

