"""Phase 2L pilot: EventLogPanel rendering."""

from __future__ import annotations

from htop_tycoon.domain import CompanyState
from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine import Event, EventKind, tick
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.widgets.event_log import EventLogPanel


def test_event_log_empty_state() -> None:
    panel = EventLogPanel(CompanyState())
    text = panel.render()
    assert "이벤트 로그" in text
    assert "아직 이벤트 없음" in text


def test_event_log_renders_recent_events() -> None:
    from htop_tycoon.domain import Money as M

    state = CompanyState(strategy=StrategyKind.AGGRESSIVE, cash=M(100_000_00))
    new_state = tick(state, GameRng(0))
    panel = EventLogPanel(new_state)
    text = panel.render()
    assert "이벤트 로그" in text


def test_event_log_max_visible_caps_at_5() -> None:
    """Even with many events, render shows at most 5 lines."""
    from htop_tycoon.domain import Money as M
    from htop_tycoon.domain.enums import StrategyKind

    state = CompanyState(strategy=StrategyKind.AGGRESSIVE, cash=M(100_000_00))
    for _ in range(20):
        state = tick(state, GameRng(0))
    panel = EventLogPanel(state)
    text = panel.render()
    line_count = len([ln for ln in text.splitlines() if ln.strip()])
    assert line_count <= 6


def test_event_log_appended_after_tick() -> None:
    """After a tick, event_log should have new events."""
    from htop_tycoon.domain import Money as M

    state = CompanyState(strategy=StrategyKind.AGGRESSIVE, cash=M(100_000_00))
    initial_log_len = len(state.event_log)
    new_state = tick(state, GameRng(0))
    assert len(new_state.event_log) > initial_log_len


def test_event_log_app_mounts_widget() -> None:
    """App compose() mounts an EventLogPanel Static widget in the body."""
    import asyncio

    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    async def _check() -> None:
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause()
            contents = [
                str(getattr(w, "content", ""))
                for w in app.screen.walk_children()
                if w.__class__.__name__ == "Static"
            ]
            assert any("이벤트 로그" in c for c in contents), (
                f"EventLogPanel not mounted. Contents: {contents}"
            )

    asyncio.run(_check())


def test_event_log_renders_with_app() -> None:
    """Full app: event log visible in body after tick."""
    import asyncio

    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    async def _tick() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # Switch to aggressive to force events
            app.action_select_strategy("AGGRESSIVE")
            await pilot.pause()
            app._advance_one_tick()
            await pilot.pause()
            assert len(app._state.event_log) > 0

    asyncio.run(_tick())


def test_event_frozen() -> None:
    """Event is frozen — cannot mutate after creation."""
    from dataclasses import FrozenInstanceError

    import pytest

    e = Event(day_index=1, year=1, kind=EventKind.HIRE, description="test")
    with pytest.raises(FrozenInstanceError):
        e.description = "modified"  # type: ignore[misc]
