"""Tests for HR auto-execute: zombie fire + auto promote."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Employee,
    EmployeeId,
    Job,
    Money,
)
from htop_tycoon.domain.enums import Department
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine.auto import auto_execute
from htop_tycoon.engine.market import MarketState


def _emp(eid: int, name: str, satisfaction: int = 80, job: Job = Job.JUNIOR, level: int = 1, dept: Department = Department.DEV) -> Employee:
    return Employee(
        id=EmployeeId(eid),
        name=f"{name}{eid}",
        job=job,
        level=level,
        salary=Money(200_00),
        satisfaction=satisfaction,
        dept=dept,
    )


def _market() -> MarketState:
    return MarketState.default_for_platform(__import__("htop_tycoon.domain").domain.Platform.PC)


def test_auto_fire_zombie_even_when_cash_is_high() -> None:
    """cash가 $50k여도 좀비 직원이 있으면 자동 해고 (사용자 보고: 좀비 방치)."""
    state = CompanyState(cash=Money(50_000_00), auto_on=True)
    state = state.add_employee(_emp(1, "Zombie", satisfaction=10))

    new_state = auto_execute(state, GameRng(0), _market())
    assert EmployeeId(1) not in new_state.employees, (
        f"Zombie should be fired regardless of cash; got {list(new_state.employees)}"
    )


def test_no_fire_when_no_zombie() -> None:
    state = CompanyState(cash=Money(50_000_00), auto_on=True)
    state = state.add_employee(_emp(1, "Happy", satisfaction=80))

    new_state = auto_execute(state, GameRng(0), _market())
    assert EmployeeId(1) in new_state.employees


def test_auto_promote_lead_with_high_satisfaction() -> None:
    """LEAD + 만족도 80%+ + level < 10이면 자동 승진 (사용자 보고: 승진 방치)."""
    state = CompanyState(cash=Money(100_000_00), auto_on=True)
    state = state.add_employee(
        _emp(1, "Star", satisfaction=85, job=Job.LEAD, level=5)
    )

    new_state = auto_execute(state, GameRng(0), _market())
    promoted = new_state.employees[EmployeeId(1)]
    assert promoted.level == 6, (
        f"Star should auto-promote from L5 to L6, got L{promoted.level}"
    )


def test_no_promote_when_satisfaction_too_low() -> None:
    """LEAD이지만 만족도 80% 미만이면 자동 승진 안 함."""
    state = CompanyState(cash=Money(100_000_00), auto_on=True)
    state = state.add_employee(
        _emp(1, "SadLead", satisfaction=70, job=Job.LEAD, level=5)
    )

    new_state = auto_execute(state, GameRng(0), _market())
    assert new_state.employees[EmployeeId(1)].level == 5


def test_no_promote_when_at_max_level() -> None:
    """LEAD + 만족도 80%+ 이지만 이미 max level이면 승진 안 함."""
    state = CompanyState(cash=Money(100_000_00), auto_on=True)
    state = state.add_employee(
        _emp(1, "MaxLead", satisfaction=85, job=Job.LEAD, level=10)
    )

    new_state = auto_execute(state, GameRng(0), _market())
    assert new_state.employees[EmployeeId(1)].level == 10


def test_promote_records_event() -> None:
    """자동 승진 시 event_log에 기록."""
    state = CompanyState(cash=Money(100_000_00), auto_on=True)
    state = state.add_employee(
        _emp(1, "Star", satisfaction=85, job=Job.LEAD, level=5)
    )

    new_state = auto_execute(state, GameRng(0), _market())
    promote_events = [
        e for e in new_state.event_log
        if hasattr(e, "description") and "승진" in e.description
    ]
    assert len(promote_events) >= 1, (
        f"Expected at least one promote event, got {[e.description for e in new_state.event_log]}"
    )