"""Tests for T5: domain.dept (DepartmentType + Department) and domain.employee (Employee).

Locks the contract:
- DepartmentType has exactly 5 locked values: Engineering, Sales, Operations, Marketing, Finance.
- Department is a frozen dataclass with id, type, head_employee_id, employee_ids,
  founded_tick, unlocked; rejects duplicate employee_ids and rejects a head_employee_id
  not in employee_ids.
- Employee is a frozen dataclass; validates skill in [1, 10], tier in [1, 5],
  satisfaction in [0, 100]; promote() and demote() return NEW instances via
  dataclasses.replace (immutability preserved); salary scales by
  balance.yaml money.salary_tier_multiplier.
"""

from __future__ import annotations

import dataclasses
from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.state import DepartmentId, EmployeeId

# -- DepartmentType ----------------------------------------------------------


class TestDepartmentTypeEnum:
    """DepartmentType is a locked enum of exactly 5 values."""

    def test_has_exactly_five_values(self) -> None:
        """Given: the locked enum
        When: counted
        Then: exactly 5 members
        """
        assert len(DepartmentType) == 5

    def test_contains_engineering(self) -> None:
        """Engineering must be a member."""
        assert hasattr(DepartmentType, "Engineering")

    def test_contains_sales(self) -> None:
        """Sales must be a member."""
        assert hasattr(DepartmentType, "Sales")

    def test_contains_operations(self) -> None:
        """Operations must be a member."""
        assert hasattr(DepartmentType, "Operations")

    def test_contains_marketing(self) -> None:
        """Marketing must be a member."""
        assert hasattr(DepartmentType, "Marketing")

    def test_contains_finance(self) -> None:
        """Finance must be a member."""
        assert hasattr(DepartmentType, "Finance")

    def test_member_values_are_strings(self) -> None:
        """Each member must have a string value (serializable)."""
        for member in DepartmentType:
            assert isinstance(member.value, str)
            assert member.value  # non-empty

    def test_member_names_match_value_strings(self) -> None:
        """Member name == member value (canonical naming)."""
        for member in DepartmentType:
            assert member.name == member.value


# -- Department --------------------------------------------------------------


def _make_emp_id(value: str) -> EmployeeId:
    """Test helper to build an EmployeeId from a string."""
    return EmployeeId(value)


def _make_dept_id(value: str) -> DepartmentId:
    """Test helper to build a DepartmentId from a string."""
    return DepartmentId(value)


class TestDepartmentCreation:
    """Department can be created with valid inputs."""

    def test_creates_minimal_department(self) -> None:
        """Given: valid args (no head, no employees)
        When: Department is constructed
        Then: holds the values as given
        """
        d = Department(
            id=_make_dept_id("dept-eng"),
            type=DepartmentType.Engineering,
            head_employee_id=None,
            employee_ids=[],
            founded_tick=0,
        )
        assert d.id == "dept-eng"
        assert d.type is DepartmentType.Engineering
        assert d.head_employee_id is None
        assert d.employee_ids == []
        assert d.founded_tick == 0

    def test_default_unlocked_is_false(self) -> None:
        """Given: no unlocked arg supplied
        When: Department is constructed
        Then: unlocked defaults to False (T8 SECRET ending gate)
        """
        d = Department(
            id=_make_dept_id("dept-eng"),
            type=DepartmentType.Engineering,
            head_employee_id=None,
            employee_ids=[],
            founded_tick=0,
        )
        assert d.unlocked is False

    def test_creates_department_with_head_and_employees(self) -> None:
        """Given: head + employee_ids
        When: Department is constructed
        Then: holds them as given (with head in employee_ids)
        """
        eid = _make_emp_id("emp-1")
        d = Department(
            id=_make_dept_id("dept-eng"),
            type=DepartmentType.Engineering,
            head_employee_id=eid,
            employee_ids=[eid],
            founded_tick=5,
            unlocked=True,
        )
        assert d.head_employee_id == eid
        assert d.employee_ids == [eid]
        assert d.founded_tick == 5
        assert d.unlocked is True

    def test_department_is_frozen(self) -> None:
        """Given: a Department
        When: a field is reassigned
        Then: raises FrozenInstanceError
        """
        d = Department(
            id=_make_dept_id("dept-eng"),
            type=DepartmentType.Engineering,
            head_employee_id=None,
            employee_ids=[],
            founded_tick=0,
        )
        with pytest.raises(FrozenInstanceError):
            d.founded_tick = 1  # type: ignore[misc]

    def test_dataclasses_replace_preserves_immutability(self) -> None:
        """Given: a Department
        When: dataclasses.replace is used
        Then: original is unchanged; new instance has updated fields
        """
        d = Department(
            id=_make_dept_id("dept-eng"),
            type=DepartmentType.Engineering,
            head_employee_id=None,
            employee_ids=[],
            founded_tick=0,
        )
        d2 = dataclasses.replace(d, unlocked=True)
        assert d.unlocked is False  # original untouched
        assert d2.unlocked is True  # new instance has updated value
        assert d2.id == d.id  # other fields preserved


class TestDepartmentValidation:
    """Department rejects invalid construction inputs."""

    def test_rejects_duplicate_employee_ids(self) -> None:
        """Given: employee_ids with duplicates
        When: Department is constructed
        Then: ValueError
        """
        with pytest.raises(ValueError, match="employee_ids"):
            Department(
                id=_make_dept_id("dept-eng"),
                type=DepartmentType.Engineering,
                head_employee_id=None,
                employee_ids=[_make_emp_id("emp-1"), _make_emp_id("emp-1")],
                founded_tick=0,
            )

    def test_rejects_head_not_in_employee_ids(self) -> None:
        """Given: head_employee_id not in employee_ids
        When: Department is constructed
        Then: ValueError
        """
        with pytest.raises(ValueError, match="head_employee_id"):
            Department(
                id=_make_dept_id("dept-eng"),
                type=DepartmentType.Engineering,
                head_employee_id=_make_emp_id("emp-head"),
                employee_ids=[_make_emp_id("emp-1")],  # emp-head not here
                founded_tick=0,
            )

    def test_accepts_head_in_employee_ids(self) -> None:
        """Given: head is one of the employees
        When: Department is constructed
        Then: no error
        """
        head = _make_emp_id("emp-head")
        emp = _make_emp_id("emp-1")
        d = Department(
            id=_make_dept_id("dept-eng"),
            type=DepartmentType.Engineering,
            head_employee_id=head,
            employee_ids=[emp, head],
            founded_tick=0,
        )
        assert d.head_employee_id == head
        assert head in d.employee_ids


# -- Employee ----------------------------------------------------------------


def _sample_employee(**overrides: object) -> Employee:
    """Build a valid Employee; tests pass keyword overrides."""
    defaults: dict[str, object] = {
        "id": _make_emp_id("emp-1"),
        "name": "Test User",
        "dept_id": _make_dept_id("dept-eng"),
        "skill": 5,
        "tier": 1,
        "salary_per_week": 1000,
        "satisfaction": 60,
        "hired_tick": 0,
    }
    defaults.update(overrides)
    return Employee(**defaults)  # type: ignore[arg-type]


class TestEmployeeCreation:
    """Employee can be created with valid inputs."""

    def test_creates_minimal_employee(self) -> None:
        """Given: valid args at boundary values
        When: Employee is constructed
        Then: holds the values
        """
        e = _sample_employee()
        assert e.id == "emp-1"
        assert e.name == "Test User"
        assert e.dept_id == "dept-eng"
        assert e.skill == 5
        assert e.tier == 1
        assert e.salary_per_week == 1000
        assert e.satisfaction == 60
        assert e.hired_tick == 0

    def test_employee_is_frozen(self) -> None:
        """Given: an Employee
        When: a field is reassigned
        Then: raises FrozenInstanceError
        """
        e = _sample_employee()
        with pytest.raises(FrozenInstanceError):
            e.tier = 5  # type: ignore[misc]


class TestEmployeeValidation:
    """Employee rejects out-of-range inputs."""

    @pytest.mark.parametrize("bad_skill", [0, -1, 11, 100])
    def test_rejects_skill_below_or_above_range(self, bad_skill: int) -> None:
        """skill must be in [1, 10]."""
        with pytest.raises(ValueError, match="skill"):
            _sample_employee(skill=bad_skill)

    @pytest.mark.parametrize("good_skill", [1, 5, 10])
    def test_accepts_skill_boundaries(self, good_skill: int) -> None:
        """skill=1 and skill=10 are valid boundaries."""
        e = _sample_employee(skill=good_skill)
        assert e.skill == good_skill

    @pytest.mark.parametrize("bad_tier", [0, -1, 6, 100])
    def test_rejects_tier_below_or_above_range(self, bad_tier: int) -> None:
        """tier must be in [1, 5]."""
        with pytest.raises(ValueError, match="tier"):
            _sample_employee(tier=bad_tier)

    @pytest.mark.parametrize("good_tier", [1, 3, 5])
    def test_accepts_tier_boundaries(self, good_tier: int) -> None:
        """tier=1 and tier=5 are valid boundaries."""
        e = _sample_employee(tier=good_tier)
        assert e.tier == good_tier

    @pytest.mark.parametrize("bad_satisfaction", [-1, -50, 101, 200])
    def test_rejects_satisfaction_below_or_above_range(self, bad_satisfaction: int) -> None:
        """satisfaction must be in [0, 100]."""
        with pytest.raises(ValueError, match="satisfaction"):
            _sample_employee(satisfaction=bad_satisfaction)

    @pytest.mark.parametrize("good_satisfaction", [0, 50, 100])
    def test_accepts_satisfaction_boundaries(self, good_satisfaction: int) -> None:
        """satisfaction=0 and satisfaction=100 are valid boundaries."""
        e = _sample_employee(satisfaction=good_satisfaction)
        assert e.satisfaction == good_satisfaction


# -- promote / demote --------------------------------------------------------


class TestEmployeePromote:
    """Employee.promote() returns a new Employee with tier+1 and salary * multiplier."""

    def test_promote_increments_tier(self) -> None:
        """Given: tier=1
        When: promote()
        Then: new Employee has tier=2
        """
        e = _sample_employee(tier=1, salary_per_week=1000)
        promoted = e.promote()
        assert promoted.tier == 2
        assert promoted.id == e.id
        assert promoted.dept_id == e.dept_id
        assert promoted.skill == e.skill
        assert promoted.satisfaction == e.satisfaction

    def test_promote_multiplies_salary_by_balance_multiplier(self) -> None:
        """Given: tier=1, salary=1000, multiplier=1.25 from balance
        When: promote()
        Then: new salary == 1000 * 1.25 == 1250 (exact, integer arithmetic)
        """
        balance = load_balance()
        multiplier = float(balance["money"]["salary_tier_multiplier"])
        assert multiplier == 1.25  # pin balance value

        e = _sample_employee(tier=1, salary_per_week=1000)
        promoted = e.promote()
        expected_salary = int(round(1000 * 1.25))
        assert promoted.salary_per_week == expected_salary
        assert promoted.salary_per_week == 1250

    def test_promote_returns_new_instance_not_mutate(self) -> None:
        """Given: an Employee
        When: promote() is called
        Then: a NEW Employee is returned; original is unchanged
        """
        e = _sample_employee(tier=2, salary_per_week=1250)
        original_tier = e.tier
        original_salary = e.salary_per_week
        promoted = e.promote()
        assert promoted is not e
        assert e.tier == original_tier
        assert e.salary_per_week == original_salary

    def test_promote_rejects_at_max_tier(self) -> None:
        """Given: tier=5 (max)
        When: promote()
        Then: ValueError (cannot promote above max)
        """
        e = _sample_employee(tier=5, salary_per_week=3000)
        with pytest.raises(ValueError, match="tier"):
            e.promote()

    def test_promote_stacks_correctly(self) -> None:
        """Given: tier=1 salary=1000
        When: promote() twice
        Then: tier=3 salary == round(1000 * 1.25^2)
        """
        balance = load_balance()
        multiplier = float(balance["money"]["salary_tier_multiplier"])
        e = _sample_employee(tier=1, salary_per_week=1000)
        once = e.promote()
        twice = once.promote()
        assert twice.tier == 3
        expected_salary = int(round(1000 * (multiplier**2)))
        assert twice.salary_per_week == expected_salary


class TestEmployeeDemote:
    """Employee.demote() returns a new Employee with tier-1 (min 1) and salary / multiplier."""

    def test_demote_decrements_tier(self) -> None:
        """Given: tier=3
        When: demote()
        Then: new Employee has tier=2
        """
        e = _sample_employee(tier=3, salary_per_week=1563)  # 1000 * 1.25^2 ~ 1563
        demoted = e.demote()
        assert demoted.tier == 2

    def test_demote_divides_salary_by_balance_multiplier(self) -> None:
        """Given: tier=2 salary=1250, multiplier=1.25
        When: demote()
        Then: new salary == round(1250 / 1.25) == 1000
        """
        balance = load_balance()
        assert float(balance["money"]["salary_tier_multiplier"]) == 1.25
        e = _sample_employee(tier=2, salary_per_week=1250)
        demoted = e.demote()
        expected_salary = int(round(1250 / 1.25))
        assert demoted.salary_per_week == expected_salary
        assert demoted.salary_per_week == 1000

    def test_demote_returns_new_instance_not_mutate(self) -> None:
        """Given: an Employee
        When: demote() is called
        Then: a NEW Employee is returned; original is unchanged
        """
        e = _sample_employee(tier=3, salary_per_week=1563)
        original_tier = e.tier
        original_salary = e.salary_per_week
        demoted = e.demote()
        assert demoted is not e
        assert e.tier == original_tier
        assert e.salary_per_week == original_salary

    def test_demote_floors_at_tier_one(self) -> None:
        """Given: tier=1 (min)
        When: demote()
        Then: tier stays at 1 (cannot demote below 1)
        """
        e = _sample_employee(tier=1, salary_per_week=1000)
        demoted = e.demote()
        assert demoted.tier == 1
        # salary unchanged at floor (the spec says tier-1, min 1; salary / multiplier when tier > 1)
        assert demoted.salary_per_week == 1000


# -- Immutability round-trip -------------------------------------------------


def test_promote_then_demote_round_trip_preserves_salary() -> None:
    """Given: tier=1 salary=1000
    When: promote() then demote()
    Then: tier==1, salary within +-1 of original (rounding-safe round-trip)
    """
    e = _sample_employee(tier=1, salary_per_week=1000)
    promoted = e.promote()
    demoted = promoted.demote()
    assert demoted.tier == 1
    # round(1000 * 1.25 / 1.25) == 1000 exactly with round()
    assert abs(demoted.salary_per_week - 1000) <= 1


# -- Salary tier math parametrized -------------------------------------------


@pytest.mark.parametrize("target_tier", [1, 2, 3, 4, 5])
def test_salary_tier_math_chain_promotions(target_tier: int) -> None:
    """Given: a tier-1 employee with salary 1000
    When: (target_tier - 1) promotions are applied
    Then: salary matches the per-step rounded chain, AND equals
        round(1000 * multiplier^(target_tier - 1)) to within 1 unit of
        rounding drift.
    """
    balance = load_balance()
    multiplier = float(balance["money"]["salary_tier_multiplier"])
    # Start from the canonical tier-1 salary.
    e = _sample_employee(tier=1, salary_per_week=1000)
    current = e
    for _ in range(target_tier - 1):
        current = current.promote()
    assert current.tier == target_tier
    # Per-step rounding can drift from the closed-form by +/-1 unit; allow
    # that drift so the test reflects actual behavior, not ideal math.
    closed_form = int(round(1000 * (multiplier ** (target_tier - 1))))
    assert abs(current.salary_per_week - closed_form) <= 1, (
        f"tier={target_tier}: got {current.salary_per_week}, "
        f"closed_form={closed_form}, drift={current.salary_per_week - closed_form}"
    )


def test_salary_tier_math_exact_promotion_table() -> None:
    """Given: the canonical tier-1 starting salary (1000)
    When: each tier is reached by chained promotions
    Then: per-step rounded salaries match the documented table:
        tier 1 -> 1000
        tier 2 -> 1250
        tier 3 -> 1562  (Python banker's round of 1250 * 1.25 = 1562.5)
        tier 4 -> 1952  (1562 * 1.25 = 1952.5 -> 1952 by even-half rule)
        tier 5 -> 2440  (1952 * 1.25 = 2440.0)
    """
    e = _sample_employee(tier=1, salary_per_week=1000)
    expected_by_tier: dict[int, int] = {
        1: 1000,
        2: 1250,
        3: 1562,
        4: 1952,
        5: 2440,
    }
    current = e
    for tier in range(2, 6):
        current = current.promote()
        assert current.tier == tier
        assert current.salary_per_week == expected_by_tier[tier], (
            f"tier {tier}: got {current.salary_per_week}, "
            f"expected {expected_by_tier[tier]}"
        )
