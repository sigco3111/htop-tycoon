"""Tests for meta_strategy.pick_strategy — heuristic strategy selector."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
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
from htop_tycoon.engine.strategy.meta_strategy import pick_strategy


def _zombie(eid: int = 1) -> Employee:
    return Employee(
        id=EmployeeId(eid),
        name=f"Zombie{eid}",
        job=Job.QA,
        level=1,
        salary=Money(200_00),
        satisfaction=10,
        dept=Department.QA,
    )


def test_pick_conservative_when_cash_negative() -> None:
    state = CompanyState(cash=Money(-1_00), strategy=StrategyKind.BALANCED)
    assert pick_strategy(state, GameRng(0)) == StrategyKind.CONSERVATIVE


def test_pick_conservative_when_cash_low_and_zombie_exists() -> None:
    state = CompanyState(cash=Money(10_000_00), strategy=StrategyKind.AGGRESSIVE)
    state = state.add_employee(_zombie())
    assert pick_strategy(state, GameRng(0)) == StrategyKind.CONSERVATIVE


def test_pick_aggressive_when_rich_and_understaffed() -> None:
    state = CompanyState(cash=Money(150_000_00), strategy=StrategyKind.BALANCED)
    assert pick_strategy(state, GameRng(0)) == StrategyKind.AGGRESSIVE


def test_pick_genre_focus_when_focus_set_and_no_in_progress() -> None:
    state = CompanyState(
        cash=Money(50_000_00),
        strategy=StrategyKind.BALANCED,
        focus_genre=Genre.RPG,
    )
    assert pick_strategy(state, GameRng(0)) == StrategyKind.GENRE_FOCUS


def test_pick_genre_focus_when_rich_and_large_team() -> None:
    state = CompanyState(cash=Money(120_000_00), strategy=StrategyKind.BALANCED)
    for i in range(1, 8):
        state = state.add_employee(
            Employee(
                id=EmployeeId(i),
                name=f"E{i}",
                job=Job.JUNIOR,
                level=1,
                salary=Money(200_00),
                satisfaction=80,
                dept=Department.DEV,
            )
        )
    assert pick_strategy(state, GameRng(0)) == StrategyKind.GENRE_FOCUS


def test_pick_balanced_otherwise() -> None:
    state = CompanyState(cash=Money(50_000_00), strategy=StrategyKind.AGGRESSIVE)
    assert pick_strategy(state, GameRng(0)) == StrategyKind.BALANCED


def test_pick_strategy_takes_rng_without_crashing() -> None:
    """rng is reserved for future stochastic tie-breaking; verify signature accepts it."""
    state = CompanyState(cash=Money(50_000_00), strategy=StrategyKind.BALANCED)
    for seed in [0, 42, 999]:
        assert pick_strategy(state, GameRng(seed)) in list(StrategyKind)