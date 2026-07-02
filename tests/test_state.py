"""T3.1 RED: CompanyState aggregate invariants."""

from __future__ import annotations

import pytest

from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.enums import Department, Genre, Job, Platform, StrategyKind
from htop_tycoon.domain.ids import EmployeeId, GameTitle, ProjectId
from htop_tycoon.domain.money import Money
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.quality import Progress, QualityAxes
from htop_tycoon.domain.state import DEFAULT_RNG_SEED, YEAR_LENGTH_DAYS, CompanyState


def test_default_construction() -> None:
    cs = CompanyState()
    assert cs.year == 1
    assert cs.day_index == 0
    assert cs.cash == Money(100_000_00)
    assert cs.fans == 0
    assert cs.strategy == StrategyKind.BALANCED
    assert cs.auto_on is False
    assert cs.speed == 1
    assert cs.employees == {}
    assert cs.projects == {}
    assert cs.rng_seed == DEFAULT_RNG_SEED


def test_year_below_one_rejected() -> None:
    with pytest.raises(ValueError):
        CompanyState(year=0)


def test_negative_cash_allowed() -> None:
    """Debt state is legal — bankruptcy is detected later."""
    cs = CompanyState(cash=Money(-50_00))
    assert cs.cash == Money(-50_00)


def test_advance_day_increments_day_index() -> None:
    cs = CompanyState()
    advanced = cs.advance_day()
    assert advanced.day_index == 1
    assert cs.day_index == 0  # original immutable


def test_advance_day_returns_new_instance() -> None:
    cs = CompanyState()
    advanced = cs.advance_day()
    assert advanced is not cs


def test_new_year_resets_day_index() -> None:
    """After 365 days, year advances to 2 and day_index resets to 0."""
    cs = CompanyState()
    advanced = cs
    for _ in range(YEAR_LENGTH_DAYS):
        advanced = advanced.advance_day()
    assert advanced.year == 2
    assert advanced.day_index == 0


def test_add_employee() -> None:
    cs = CompanyState()
    emp = Employee(
        id=EmployeeId(1),
        name="Ada",
        job=Job.JUNIOR,
        level=1,
        salary=Money(3000_00),
        satisfaction=80,
        dept=Department.DEV,
    )
    new_cs = cs.add_employee(emp)
    assert new_cs.employees[emp.id] is emp
    assert cs.employees == {}  # original immutable


def test_add_employee_duplicate_id_rejected() -> None:
    cs = CompanyState()
    emp = Employee(
        id=EmployeeId(1),
        name="Ada",
        job=Job.JUNIOR,
        level=1,
        salary=Money(3000_00),
        satisfaction=80,
        dept=Department.DEV,
    )
    cs = cs.add_employee(emp)
    with pytest.raises(ValueError):
        cs.add_employee(emp)


def test_remove_employee() -> None:
    cs = CompanyState().add_employee(
        Employee(
            id=EmployeeId(1),
            name="Ada",
            job=Job.JUNIOR,
            level=1,
            salary=Money(3000_00),
            satisfaction=80,
            dept=Department.DEV,
        )
    )
    new_cs = cs.remove_employee(EmployeeId(1))
    assert new_cs.employees == {}
    assert EmployeeId(1) in cs.employees


def test_remove_nonexistent_employee_is_no_op() -> None:
    cs = CompanyState()
    new_cs = cs.remove_employee(EmployeeId(99))
    assert new_cs.employees == {}


def test_add_project() -> None:
    cs = CompanyState()
    proj = GameProject(
        id=ProjectId(1),
        title=GameTitle("Eldritch Quest"),
        genre=Genre.RPG,
        platform=Platform.PC,
        console=None,
        progress=Progress(0),
        quality=QualityAxes(),
        days_in_dev=0,
        lead_id=None,
        team_ids=(),
    )
    new_cs = cs.add_project(proj)
    assert new_cs.projects[proj.id] is proj


def test_remove_project() -> None:
    proj = GameProject(
        id=ProjectId(1),
        title=GameTitle("EQ"),
        genre=Genre.RPG,
        platform=Platform.PC,
        console=None,
        progress=Progress(0),
        quality=QualityAxes(),
        days_in_dev=0,
        lead_id=None,
        team_ids=(),
    )
    cs = CompanyState().add_project(proj)
    new_cs = cs.remove_project(ProjectId(1))
    assert new_cs.projects == {}


def test_set_strategy() -> None:
    cs = CompanyState()
    new_cs = cs.set_strategy(StrategyKind.AGGRESSIVE)
    assert new_cs.strategy == StrategyKind.AGGRESSIVE
    assert cs.strategy == StrategyKind.BALANCED


def test_set_speed_validates_range() -> None:
    cs = CompanyState()
    new_cs = cs.set_speed(2)
    assert new_cs.speed == 2
    with pytest.raises(ValueError):
        cs.set_speed(0)
    with pytest.raises(ValueError):
        cs.set_speed(-1)


def test_toggle_auto() -> None:
    cs = CompanyState()
    toggled = cs.toggle_auto()
    assert toggled.auto_on is True
    assert cs.auto_on is False


def test_rng_seed_recorded() -> None:
    cs = CompanyState(rng_seed=12345)
    assert cs.rng_seed == 12345


def test_year_length_constant() -> None:
    assert YEAR_LENGTH_DAYS == 365


def test_state_holds_independent_employee_dicts() -> None:
    """Adding an employee to one state must not affect another."""
    a = CompanyState()
    b = CompanyState()
    emp = Employee(
        id=EmployeeId(1),
        name="Ada",
        job=Job.JUNIOR,
        level=1,
        salary=Money(3000_00),
        satisfaction=80,
        dept=Department.DEV,
    )
    a2 = a.add_employee(emp)
    assert b.employees == {}
    assert a2.employees[EmployeeId(1)] is emp
