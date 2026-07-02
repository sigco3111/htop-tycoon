"""Tests for engine.auto.auto_execute — single-tick AI decision executor."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Console,
    Employee,
    EmployeeId,
    GameProject,
    GameTitle,
    Genre,
    Job,
    Money,
    Platform,
    Progress,
    ProjectId,
    QualityAxes,
    StrategyKind,
)
from htop_tycoon.domain.enums import Department
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine.auto import auto_execute
from htop_tycoon.engine.market import MarketState


def _emp(eid: int, name: str = "E", satisfaction: int = 80, job: Job = Job.JUNIOR) -> Employee:
    return Employee(
        id=EmployeeId(eid),
        name=f"{name}{eid}",
        job=job,
        level=1,
        salary=Money(200_00),
        satisfaction=satisfaction,
        dept=Department.DEV,
    )


def _shipped_project(pid: int = 1) -> GameProject:
    return GameProject(
        id=ProjectId(pid),
        title=GameTitle(f"Done{pid}"),
        genre=Genre.RPG,
        platform=Platform.PC,
        console=None,
        progress=Progress(100),
        quality=QualityAxes(80, 70, 60, 50),
        days_in_dev=100,
        lead_id=None,
        team_ids=(),
    )


def test_auto_execute_re_picks_strategy_when_auto_on() -> None:
    state = CompanyState(cash=Money(-1_00), auto_on=True, strategy=StrategyKind.AGGRESSIVE)
    market = MarketState.default_for_platform(Platform.PC)
    new_state = auto_execute(state, GameRng(0), market)
    assert new_state.strategy == StrategyKind.CONSERVATIVE


def test_auto_execute_hires_when_aggressive_and_rich() -> None:
    state = CompanyState(
        cash=Money(150_000_00), auto_on=True, strategy=StrategyKind.AGGRESSIVE,
    )
    market = MarketState.default_for_platform(Platform.PC)
    new_state = auto_execute(state, GameRng(0), market)
    assert len(new_state.employees) == 1


def test_auto_execute_fires_zombie_when_conservative_and_low_cash() -> None:
    state = CompanyState(cash=Money(10_000_00), auto_on=True, strategy=StrategyKind.CONSERVATIVE)
    state = state.add_employee(_emp(1, "Zombie", satisfaction=10))
    market = MarketState.default_for_platform(Platform.PC)
    new_state = auto_execute(state, GameRng(0), market)
    assert len(new_state.employees) == 0


def test_auto_execute_buys_console_when_rich_and_no_console() -> None:
    state = CompanyState(cash=Money(100_000_00), auto_on=True, strategy=StrategyKind.BALANCED)
    market = MarketState.default_for_platform(Platform.PC)
    new_state = auto_execute(state, GameRng(0), market)
    assert new_state.own_console is not None


def test_auto_execute_skips_console_when_already_owned() -> None:
    state = CompanyState(
        cash=Money(100_000_00), auto_on=True,
        strategy=StrategyKind.BALANCED, own_console=Console.ATARI_Q,
    )
    market = MarketState.default_for_platform(Platform.PC)
    new_state = auto_execute(state, GameRng(0), market)
    assert new_state.own_console == Console.ATARI_Q


def test_auto_execute_releases_shipped_project() -> None:
    state = CompanyState(
        cash=Money(50_000_00), auto_on=True,
        strategy=StrategyKind.BALANCED, own_console=Console.ATARI_Q,
    )
    state = state.add_project(_shipped_project(1))
    market = MarketState.default_for_platform(Platform.PC)
    new_state = auto_execute(state, GameRng(0), market)
    assert new_state.projects[ProjectId(1)].console is not None


def test_auto_execute_appends_events_for_actions() -> None:
    state = CompanyState(
        cash=Money(60_000_00), auto_on=True, strategy=StrategyKind.AGGRESSIVE,
    )
    market = MarketState.default_for_platform(Platform.PC)
    new_state = auto_execute(state, GameRng(0), market)
    assert len(new_state.event_log) > 0


def test_auto_execute_is_pure() -> None:
    state = CompanyState(
        cash=Money(60_000_00), auto_on=True, strategy=StrategyKind.AGGRESSIVE,
    )
    market = MarketState.default_for_platform(Platform.PC)
    initial_employees = dict(state.employees)
    initial_cash = state.cash.cents
    auto_execute(state, GameRng(0), market)
    assert state.employees == initial_employees
    assert state.cash.cents == initial_cash


def test_auto_execute_does_nothing_when_balanced_steady_state() -> None:
    """Balanced + 5 employees + active project + moderate cash → minimal action."""
    state = CompanyState(
        cash=Money(50_000_00), auto_on=True, strategy=StrategyKind.BALANCED,
        own_console=Console.ATARI_Q,
    )
    for i in range(1, 6):
        state = state.add_employee(_emp(i))
    state = state.add_project(_shipped_project(1))
    market = MarketState.default_for_platform(Platform.PC)
    new_state = auto_execute(state, GameRng(0), market)
    # Strategy may change to GENRE_FOCUS (large team + rich) but no hire/fire/console-buy
    assert new_state.own_console == Console.ATARI_Q
    assert new_state.voluntary_sale_pending is False


def test_auto_execute_voluntary_sale_when_mega_hit_and_cash_rich() -> None:
    state = CompanyState(
        cash=Money(250_000_00), auto_on=True,
        strategy=StrategyKind.BALANCED, focus_genre=None,
        voluntary_sale_pending=False, mega_hits=1,
        own_console=Console.ATARI_Q,
    )
    market = MarketState.default_for_platform(Platform.PC)
    new_state = auto_execute(state, GameRng(0), market)
    assert new_state.voluntary_sale_pending is True