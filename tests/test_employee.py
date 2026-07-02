"""T2.1 RED: Employee + Salary + compute_salary invariants."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.domain.employee import Employee, Salary, compute_salary
from htop_tycoon.domain.enums import Department, Job
from htop_tycoon.domain.ids import EmployeeId
from htop_tycoon.domain.money import Money


def _basic(**kwargs: object) -> Employee:
    defaults: dict[str, object] = {
        "id": EmployeeId(1),
        "name": "Ada",
        "job": Job.JUNIOR,
        "level": 1,
        "salary": Money(3000_00),
        "satisfaction": 80,
        "dept": Department.DEV,
    }
    defaults.update(kwargs)
    return Employee(**defaults)  # type: ignore[arg-type]


def test_employee_creation_minimal() -> None:
    e = _basic()
    assert e.id == EmployeeId(1)
    assert e.name == "Ada"
    assert e.job == Job.JUNIOR
    assert e.level == 1
    assert e.satisfaction == 80


def test_employee_level_below_one_rejected() -> None:
    with pytest.raises(ValueError):
        _basic(level=0)


def test_employee_level_above_ten_rejected() -> None:
    with pytest.raises(ValueError):
        _basic(level=11)


def test_employee_satisfaction_clamps_negative() -> None:
    e = _basic(satisfaction=-5)
    assert e.satisfaction == 0


def test_employee_satisfaction_clamps_over_100() -> None:
    e = _basic(satisfaction=150)
    assert e.satisfaction == 100


def test_employee_is_zombie_below_20() -> None:
    e = _basic(satisfaction=15)
    assert e.is_zombie is True


def test_employee_is_zombie_at_or_above_20() -> None:
    assert _basic(satisfaction=20).is_zombie is False
    assert _basic(satisfaction=100).is_zombie is False


def test_employee_promote_increments_level() -> None:
    e = _basic(level=5)
    promoted = e.promote()
    assert promoted.level == 6


def test_employee_promote_returns_new_instance() -> None:
    e = _basic(level=5)
    promoted = e.promote()
    assert e.level == 5
    assert promoted is not e


def test_employee_promote_raises_salary_15_percent() -> None:
    """Salary after promote == original * 1.15 (cent-precise)."""
    e = _basic(level=5, salary=Money(100_00))
    promoted = e.promote()
    assert promoted.salary == Money(115_00)


def test_employee_promote_at_level_10_raises() -> None:
    e = _basic(level=10)
    with pytest.raises(ValueError):
        e.promote()


def test_employee_frozen() -> None:
    e = _basic()
    with pytest.raises(FrozenInstanceError):
        e.name = "x"  # type: ignore[misc]


def test_salary_compute_returns_money_and_tier() -> None:
    s = compute_salary(Job.SENIOR, 3)
    assert isinstance(s, Salary)
    assert isinstance(s.amount, Money)
    assert isinstance(s.tier, int)
    assert s.amount.cents > 0
    assert s.tier >= 1


def test_salary_compute_deterministic() -> None:
    """Same Job + level must give same Salary."""
    a = compute_salary(Job.LEAD, 5)
    b = compute_salary(Job.LEAD, 5)
    assert a == b


def test_salary_compute_higher_level_pays_more() -> None:
    low = compute_salary(Job.JUNIOR, 1)
    high = compute_salary(Job.JUNIOR, 5)
    assert high.amount > low.amount


def test_salary_frozen() -> None:
    s = compute_salary(Job.JUNIOR, 1)
    with pytest.raises(FrozenInstanceError):
        s.amount = Money(0)  # type: ignore[misc]
