"""Phase 2K: strategy.decide() auto-applied in tick()."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Department,
    Employee,
    EmployeeId,
    Genre,
    Job,
    Money,
)
from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine import (
    Event,
    EventKind,
    current_strategy,
    tick,
)


def _emp(eid: int, satisfaction: int = 80) -> Employee:
    return Employee(
        id=EmployeeId(eid),
        name=f"Emp{eid}",
        job=Job.JUNIOR,
        level=1,
        salary=Money(200_00),
        satisfaction=satisfaction,
        dept=Department.DEV,
    )


def test_tick_records_strategy_events_in_event_log() -> None:
    """Aggressive strategy on a rich state should record HIRE events."""
    state = CompanyState(cash=Money(60_000_00), strategy=StrategyKind.AGGRESSIVE)
    new_state = tick(state, GameRng(0))
    event_kinds = {e.kind for e in new_state.event_log if isinstance(e, Event)}
    assert EventKind.HIRE in event_kinds or EventKind.START_PROJECT in event_kinds


def test_tick_auto_hires_via_strategy() -> None:
    """Aggressive strategy with rich state auto-hires an employee."""
    state = CompanyState(cash=Money(60_000_00), strategy=StrategyKind.AGGRESSIVE)
    initial_count = len(state.employees)
    new_state = tick(state, GameRng(0))
    # Aggressive fires hire(magnitude=2) but auto-apply picks 1st candidate
    assert len(new_state.employees) > initial_count


def test_tick_conservative_fires_zombie() -> None:
    """Conservative with low cash + zombie should auto-fire."""
    state = (
        CompanyState(cash=Money(10_000_00), strategy=StrategyKind.CONSERVATIVE)
        .add_employee(_emp(1, satisfaction=10))  # zombie
    )
    new_state = tick(state, GameRng(0))
    assert EmployeeId(1) not in new_state.employees
    zombie_events = [
        e for e in new_state.event_log
        if isinstance(e, Event) and e.kind == EventKind.FIRE
    ]
    assert len(zombie_events) >= 1


def test_tick_event_log_preserves_order() -> None:
    """Events are appended in decision order across the tick."""
    state = CompanyState(cash=Money(60_000_00), strategy=StrategyKind.AGGRESSIVE)
    new_state = tick(state, GameRng(0))
    day_0_events = [
        e for e in new_state.event_log
        if isinstance(e, Event) and e.day_index == 0
    ]
    assert day_0_events == sorted(day_0_events, key=lambda e: e.kind.value)


def test_tick_no_strategy_events_when_balanced_with_full_team_and_project() -> None:
    """Balanced strategy with full team + active project should not record events."""
    from htop_tycoon.domain import (
        GameProject,
        GameTitle,
        Platform,
        Progress,
        ProjectId,
        QualityAxes,
    )
    state = (
        CompanyState(cash=Money(200_000_00), strategy=StrategyKind.BALANCED)
        .add_employee(_emp(1))
        .add_employee(_emp(2))
        .add_employee(_emp(3))
        .add_employee(_emp(4))
        .add_employee(_emp(5))
        .add_project(
            GameProject(
                id=ProjectId(1),
                title=GameTitle("Active"),
                genre=Genre.RPG,
                platform=Platform.PC,
                console=None,
                progress=Progress(50),
                quality=QualityAxes(80, 80, 80, 80),
                days_in_dev=50,
                lead_id=EmployeeId(1),
                team_ids=(),
            )
        )
    )
    new_state = tick(state, GameRng(0))
    balanced_events = [
        e for e in new_state.event_log
        if isinstance(e, Event) and e.day_index == 0
    ]
    hire_or_start = [
        e for e in balanced_events
        if e.kind in (EventKind.HIRE, EventKind.START_PROJECT)
    ]
    assert len(hire_or_start) == 0


def test_current_strategy_returns_genre_focus_instance() -> None:
    from htop_tycoon.engine.strategy import GenreFocusStrategy

    state = CompanyState(strategy=StrategyKind.GENRE_FOCUS, focus_genre=Genre.RPG)
    strat = current_strategy(state)
    assert isinstance(strat, GenreFocusStrategy)
    assert strat.focus_genre == Genre.RPG


def test_event_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    import pytest

    e = Event(day_index=1, year=1, kind=EventKind.HIRE, description="test")
    with pytest.raises(FrozenInstanceError):
        e.description = "modified"  # type: ignore[misc]
