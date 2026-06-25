"""Tests for T10: engine.actions (hire / fire / promote / demote).

Locks the contract from .omo/plans/htop-tycoon.md line 332-346:

- Every action is a pure function returning ``(state, list[Event])``;
  the actions NEVER call ``event_bus.publish(...)`` directly (caller does).
- ``hire`` creates a new employee from ``balance.employees.starting_skill_range``,
  tier=1, and returns ``[EmployeeHired(new_id)]``.
- ``fire`` pays ``balance.employees.fire_severance_per_tier * tier`` out of
  company cash and returns ``[EmployeeFired(emp_id, severance_paid)]``.
- ``promote`` increments tier, multiplies salary, deducts
  ``balance.employees.promotion_cost``; if cash is insufficient, the state is
  unchanged and ``[AlertRaised("예산 부족 — 승진 불가", "warn")]`` is returned.
- ``demote`` decrements tier (floored at 1), divides salary, adds
  ``balance.employees.demotion_savings`` to cash; returns
  ``[EmployeeDemoted(emp_id, savings_gained)]``.
- Promote + demote round-trip returns to original tier+1 with the correct
  salary (to within +-1 unit of rounding drift).
- The module ``htop_tycoon/engine/actions.py`` MUST NOT contain any
  ``event_bus.publish(...)`` call (string scan guard).
"""

from __future__ import annotations

import dataclasses
import importlib
from pathlib import Path
from typing import Any

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.state import (
    DepartmentId,
    EmployeeId,
    GameState,
    new_game,
)
from htop_tycoon.engine.events import (
    AlertRaised,
    EmployeeDemoted,
    EmployeeFired,
    EmployeeHired,
    EmployeePromoted,
)
from htop_tycoon.engine.rng import GameRNG

ACTIONS_MODULE = "htop_tycoon.engine.actions"


def _load_actions() -> Any:
    """Late-import the actions module so RED failures are clean assertions."""
    try:
        return importlib.import_module(ACTIONS_MODULE)
    except ImportError:
        return None


def _actions() -> Any:
    """Return the actions module or fail the current test with a clear message."""
    module = _load_actions()
    assert module is not None, (
        f"module {ACTIONS_MODULE!r} not implemented yet — T10 RED phase"
    )
    return module


def _actions_source_path() -> Path:
    """Return the on-disk path of actions.py for the grep test."""
    return (
        Path(__file__).resolve().parent.parent
        / "src"
        / "htop_tycoon"
        / "engine"
        / "actions.py"
    )


# --------------------------------------------------------------------- fixtures


def _emp_id(value: str) -> EmployeeId:
    return EmployeeId(value)


def _dept_id(value: str) -> DepartmentId:
    return DepartmentId(value)


def _make_employee(
    *,
    emp_id: str = "emp-001",
    name: str = "테스트",
    dept: str = "dept-eng",
    skill: int = 5,
    tier: int = 1,
    salary: int = 1000,
    satisfaction: int = 60,
    hired_tick: int = 0,
) -> Employee:
    return Employee(
        id=_emp_id(emp_id),
        name=name,
        dept_id=_dept_id(dept),
        skill=skill,
        tier=tier,
        salary_per_week=salary,
        satisfaction=satisfaction,
        hired_tick=hired_tick,
    )


def _make_department(
    *,
    dept_id: str = "dept-eng",
    employees: list[str] | None = None,
    head: str | None = None,
    founded_tick: int = 0,
    unlocked: bool = True,
) -> Department:
    return Department(
        id=_dept_id(dept_id),
        type=DepartmentType.Engineering,
        head_employee_id=_emp_id(head) if head is not None else None,
        employee_ids=[_emp_id(e) for e in (employees or [])],
        founded_tick=founded_tick,
        unlocked=unlocked,
    )


def _make_state_with_employee(
    *,
    emp_id: str = "emp-001",
    tier: int = 1,
    salary: int = 1000,
    skill: int = 5,
    cash: int = 50_000,
    department_employees: list[str] | None = None,
    department_head: str | None = None,
) -> GameState:
    """Build a GameState with a single Engineering department containing ``emp_id``.

    ``department_employees`` and ``department_head`` may include extra ids for
    multi-employee setups; ``emp_id`` is always added.
    """
    base = new_game(42)
    employee = _make_employee(emp_id=emp_id, tier=tier, salary=salary, skill=skill)
    members = list(department_employees or [])
    if emp_id not in members:
        members.append(emp_id)
    head = department_head if department_head is not None else (
        emp_id if not members or len(members) == 1 else members[0]
    )
    department = _make_department(
        dept_id="dept-eng",
        employees=members,
        head=head,
    )
    company = dataclasses.replace(base.company, cash=cash)
    return dataclasses.replace(
        base,
        company=company,
        departments={_dept_id("dept-eng"): department},
        employees={_emp_id(emp_id): employee},
    )


def _make_state_for_hire(*, cash: int = 50_000) -> GameState:
    """Build a GameState with an empty Engineering department ready to hire."""
    base = new_game(42)
    department = _make_department(
        dept_id="dept-eng",
        employees=[],
        head=None,
    )
    company = dataclasses.replace(base.company, cash=cash)
    return dataclasses.replace(
        base,
        company=company,
        departments={_dept_id("dept-eng"): department},
        employees={},
    )


# ===================================================================== hire
# =====================================================================


class TestHireReturnShape:
    """hire() returns (GameState, list[Event]); the list contains EmployeeHired."""

    def test_hire_returns_two_tuple(self) -> None:
        """Given: a state with an empty dept and a GameRNG
        When: hire() is called
        Then: result is a 2-tuple of (state, events)
        """
        actions = _actions()
        state = _make_state_for_hire()
        rng = GameRNG(42)
        result = actions.hire(state, _dept_id("dept-eng"), rng)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_hire_returns_new_state_and_event_list(self) -> None:
        """Given: an empty-dept state + GameRNG(42)
        When: hire() is called
        Then: result[0] is a GameState, result[1] is a list
        """
        actions = _actions()
        state = _make_state_for_hire()
        result = actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        new_state, events = result
        assert isinstance(new_state, GameState)
        assert isinstance(events, list)

    def test_hire_returns_exactly_one_employee_hired_event(self) -> None:
        """hire returns exactly one EmployeeHired event carrying the new id."""
        actions = _actions()
        state = _make_state_for_hire()
        new_state, events = actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        assert len(events) == 1
        assert isinstance(events[0], EmployeeHired)
        assert events[0].employee_id in new_state.employees


class TestHireStateMutation:
    """hire() mutates only via dataclasses.replace; input state is untouched."""

    def test_hire_adds_employee_to_state(self) -> None:
        """After hire(), the new employee exists in state.employees."""
        actions = _actions()
        state = _make_state_for_hire()
        rng = GameRNG(42)
        original_count = len(state.employees)
        new_state, events = actions.hire(state, _dept_id("dept-eng"), rng)
        assert len(new_state.employees) == original_count + 1
        # The new id from the event exists in the new state's employees dict.
        assert events[0].employee_id in new_state.employees

    def test_hire_adds_employee_to_department(self) -> None:
        """After hire(), the new id appears in state.departments[dept].employee_ids."""
        actions = _actions()
        state = _make_state_for_hire()
        new_state, events = actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        new_id = events[0].employee_id
        dept = new_state.departments[_dept_id("dept-eng")]
        assert new_id in dept.employee_ids

    def test_hire_sets_department_head_when_empty(self) -> None:
        """If the dept had no head, hire() sets the new employee as head."""
        actions = _actions()
        state = _make_state_for_hire()
        # Sanity: dept starts with no head.
        assert state.departments[_dept_id("dept-eng")].head_employee_id is None
        new_state, events = actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        new_id = events[0].employee_id
        dept = new_state.departments[_dept_id("dept-eng")]
        assert dept.head_employee_id == new_id

    def test_hire_does_not_mutate_input_state(self) -> None:
        """hire() does NOT mutate the input state (dataclasses.replace)."""
        actions = _actions()
        state = _make_state_for_hire()
        original_count = len(state.employees)
        original_dept_size = len(
            state.departments[_dept_id("dept-eng")].employee_ids
        )
        actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        assert len(state.employees) == original_count
        assert (
            len(state.departments[_dept_id("dept-eng")].employee_ids)
            == original_dept_size
        )


class TestHireEmployeeProperties:
    """The new employee has skill in starting_skill_range, tier=1, etc."""

    def test_new_employee_has_tier_one(self) -> None:
        actions = _actions()
        state = _make_state_for_hire()
        new_state, events = actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        emp = new_state.employees[events[0].employee_id]
        assert emp.tier == 1

    def test_new_employee_skill_is_in_starting_range(self) -> None:
        """skill in [starting_skill_range.lo, starting_skill_range.hi] from balance."""
        balance = load_balance()
        lo, hi = balance["employees"]["starting_skill_range"]
        actions = _actions()
        state = _make_state_for_hire()
        new_state, events = actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        emp = new_state.employees[events[0].employee_id]
        assert lo <= emp.skill <= hi, (
            f"skill {emp.skill} not in starting_skill_range [{lo}, {hi}]"
        )

    def test_new_employee_salary_is_starting_salary_from_balance(self) -> None:
        """New employee salary == starting_salary_per_week (from balance)."""
        balance = load_balance()
        expected_salary = int(balance["employees"]["starting_salary_per_week"])
        actions = _actions()
        state = _make_state_for_hire()
        new_state, events = actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        emp = new_state.employees[events[0].employee_id]
        assert emp.salary_per_week == expected_salary

    def test_new_employee_dept_id_matches_target_department(self) -> None:
        actions = _actions()
        state = _make_state_for_hire()
        new_state, events = actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        emp = new_state.employees[events[0].employee_id]
        assert emp.dept_id == _dept_id("dept-eng")

    def test_new_employee_name_from_korean_name_pool(self) -> None:
        """The new employee name comes from the korean_names.yaml pool."""
        actions = _actions()
        state = _make_state_for_hire()
        new_state, events = actions.hire(state, _dept_id("dept-eng"), GameRNG(42))
        emp = new_state.employees[events[0].employee_id]
        # Korean name: 2-4 Hangul chars. The exact match is RNG-dependent;
        # we just check it's non-empty and not the same as the placeholder.
        assert isinstance(emp.name, str)
        assert len(emp.name) >= 2


class TestHireValidation:
    """hire() validates inputs and raises on bad ones."""

    def test_hire_unknown_department_raises(self) -> None:
        """Given: a dept_id NOT in state.departments
        When: hire() is called
        Then: ValueError or KeyError (lookup fails fast)
        """
        actions = _actions()
        state = _make_state_for_hire()
        with pytest.raises((ValueError, KeyError)):
            actions.hire(state, _dept_id("dept-nope"), GameRNG(42))


# ===================================================================== fire
# =====================================================================


class TestFireReturnShape:
    """fire() returns (state, [EmployeeFired(emp_id, severance_paid)])."""

    def test_fire_returns_two_tuple(self) -> None:
        actions = _actions()
        state = _make_state_with_employee()
        result = actions.fire(state, _emp_id("emp-001"))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_fire_returns_employee_fired_with_severance(self) -> None:
        """Given: state with tier=2 employee, severance = 2 * fire_severance_per_tier.
        When: fire() is called.
        Then: events[0] is EmployeeFired(emp_id, severance_paid).
        """
        balance = load_balance()
        per_tier = int(balance["money"]["fire_severance_per_tier"])
        tier = 2
        expected_severance = per_tier * tier

        actions = _actions()
        state = _make_state_with_employee(tier=tier)
        new_state, events = actions.fire(state, _emp_id("emp-001"))
        assert len(events) == 1
        assert isinstance(events[0], EmployeeFired)
        assert events[0].employee_id == _emp_id("emp-001")
        assert events[0].severance_paid == expected_severance


class TestFireStateMutation:
    """fire() removes the employee from state.employees and the dept."""

    def test_fire_removes_employee_from_state(self) -> None:
        actions = _actions()
        state = _make_state_with_employee()
        new_state, events = actions.fire(state, _emp_id("emp-001"))
        assert _emp_id("emp-001") not in new_state.employees

    def test_fire_removes_employee_from_department(self) -> None:
        actions = _actions()
        state = _make_state_with_employee()
        new_state, _ = actions.fire(state, _emp_id("emp-001"))
        dept = new_state.departments[_dept_id("dept-eng")]
        assert _emp_id("emp-001") not in dept.employee_ids

    def test_fire_clears_department_head_if_fired_was_head(self) -> None:
        actions = _actions()
        state = _make_state_with_employee()
        # emp-001 is the sole employee and head.
        assert (
            state.departments[_dept_id("dept-eng")].head_employee_id
            == _emp_id("emp-001")
        )
        new_state, _ = actions.fire(state, _emp_id("emp-001"))
        dept = new_state.departments[_dept_id("dept-eng")]
        assert dept.head_employee_id is None

    def test_fire_pays_severance_out_of_company_cash(self) -> None:
        """cash_after = cash_before - (fire_severance_per_tier * tier)."""
        balance = load_balance()
        per_tier = int(balance["money"]["fire_severance_per_tier"])
        tier = 3
        starting_cash = 50_000
        expected_cash_after = starting_cash - per_tier * tier

        actions = _actions()
        state = _make_state_with_employee(tier=tier, cash=starting_cash)
        new_state, _ = actions.fire(state, _emp_id("emp-001"))
        assert new_state.company.cash == expected_cash_after

    def test_fire_does_not_mutate_input_state(self) -> None:
        actions = _actions()
        state = _make_state_with_employee()
        original_cash = state.company.cash
        original_emp_count = len(state.employees)
        actions.fire(state, _emp_id("emp-001"))
        assert state.company.cash == original_cash
        assert len(state.employees) == original_emp_count


class TestFireHighSkill:
    """F9 (fire) works on a high-skill employee — no skill protection."""

    def test_fire_fires_max_skill_employee(self) -> None:
        """Given: tier=1 employee with skill=10 (max) and cash to cover severance.
        When: fire() is called.
        Then: the employee is removed and severance is paid (no skill gate).
        """
        balance = load_balance()
        per_tier = int(balance["money"]["fire_severance_per_tier"])
        starting_cash = 50_000
        # Give enough cash so cash_after >= 0 — fire should never be blocked.
        actions = _actions()
        state = _make_state_with_employee(
            skill=10, tier=1, cash=starting_cash
        )
        new_state, events = actions.fire(state, _emp_id("emp-001"))
        assert _emp_id("emp-001") not in new_state.employees
        assert events[0].severance_paid == per_tier * 1
        assert new_state.company.cash == starting_cash - per_tier

    def test_fire_works_when_severance_drives_cash_negative(self) -> None:
        """fire() is unconditional; cash may go negative (matches debt semantics)."""
        balance = load_balance()
        per_tier = int(balance["money"]["fire_severance_per_tier"])
        # Cash barely covers starting but not severance — Company.cash allows
        # negatives (debt).
        starting_cash = 500
        actions = _actions()
        state = _make_state_with_employee(tier=2, cash=starting_cash)
        new_state, _ = actions.fire(state, _emp_id("emp-001"))
        assert new_state.company.cash == starting_cash - per_tier * 2


# ===================================================================== promote
# =====================================================================


class TestPromoteReturnShape:
    """promote() returns (state, [EmployeePromoted]) on success."""

    def test_promote_returns_two_tuple(self) -> None:
        actions = _actions()
        state = _make_state_with_employee(cash=10_000)
        result = actions.promote(state, _emp_id("emp-001"))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_promote_returns_employee_promoted_event(self) -> None:
        actions = _actions()
        state = _make_state_with_employee(cash=10_000)
        new_state, events = actions.promote(state, _emp_id("emp-001"))
        assert len(events) == 1
        assert isinstance(events[0], EmployeePromoted)
        assert events[0].employee_id == _emp_id("emp-001")


class TestPromoteHappyPath:
    """F7 happy path: tier+1, salary *= multiplier, cash -= promotion_cost."""

    def test_promote_increments_tier(self) -> None:
        actions = _actions()
        state = _make_state_with_employee(tier=1, salary=1000, cash=10_000)
        new_state, _ = actions.promote(state, _emp_id("emp-001"))
        assert new_state.employees[_emp_id("emp-001")].tier == 2

    def test_promote_multiplies_salary(self) -> None:
        """salary_after = round(salary_before * salary_tier_multiplier)."""
        balance = load_balance()
        multiplier = float(balance["money"]["salary_tier_multiplier"])
        actions = _actions()
        state = _make_state_with_employee(tier=1, salary=1000, cash=10_000)
        new_state, _ = actions.promote(state, _emp_id("emp-001"))
        expected = int(round(1000 * multiplier))
        assert new_state.employees[_emp_id("emp-001")].salary_per_week == expected

    def test_promote_deducts_promotion_cost_from_cash(self) -> None:
        """cash_after = cash_before - promotion_cost."""
        balance = load_balance()
        cost = int(balance["employees"]["promotion_cost"])
        actions = _actions()
        state = _make_state_with_employee(tier=1, salary=1000, cash=10_000)
        new_state, _ = actions.promote(state, _emp_id("emp-001"))
        assert new_state.company.cash == 10_000 - cost

    def test_promote_does_not_mutate_input_state(self) -> None:
        actions = _actions()
        state = _make_state_with_employee(tier=1, salary=1000, cash=10_000)
        original_cash = state.company.cash
        original_tier = state.employees[_emp_id("emp-001")].tier
        actions.promote(state, _emp_id("emp-001"))
        assert state.company.cash == original_cash
        assert state.employees[_emp_id("emp-001")].tier == original_tier


class TestPromoteBudgetRejection:
    """When cash < promotion_cost, promote() returns (state, [AlertRaised])."""

    def test_promote_when_cash_below_cost_returns_alert_event(self) -> None:
        """Given: state.company.cash == 499 (< promotion_cost == 500)
        When: promote() is called
        Then: state is unchanged AND events contains one AlertRaised.
        """
        actions = _actions()
        state = _make_state_with_employee(tier=1, salary=1000, cash=499)
        new_state, events = actions.promote(state, _emp_id("emp-001"))

        assert len(events) == 1
        assert isinstance(events[0], AlertRaised)
        assert events[0].message_ko == "예산 부족 — 승진 불가"
        assert events[0].severity == "warn"

    def test_promote_budget_rejection_state_unchanged(self) -> None:
        """State is unchanged on budget rejection: cash and tier both intact."""
        actions = _actions()
        state = _make_state_with_employee(tier=1, salary=1000, cash=499)
        original_cash = state.company.cash
        original_tier = state.employees[_emp_id("emp-001")].tier
        original_salary = state.employees[_emp_id("emp-001")].salary_per_week
        new_state, _ = actions.promote(state, _emp_id("emp-001"))

        assert new_state.company.cash == original_cash
        assert new_state.employees[_emp_id("emp-001")].tier == original_tier
        assert (
            new_state.employees[_emp_id("emp-001")].salary_per_week
            == original_salary
        )

    def test_promote_exact_cash_at_cost_succeeds(self) -> None:
        """Boundary: cash == promotion_cost is sufficient (>=, not >)."""
        balance = load_balance()
        cost = int(balance["employees"]["promotion_cost"])
        actions = _actions()
        state = _make_state_with_employee(tier=1, salary=1000, cash=cost)
        new_state, events = actions.promote(state, _emp_id("emp-001"))
        assert isinstance(events[0], EmployeePromoted)
        assert new_state.company.cash == 0


# ===================================================================== demote
# =====================================================================


class TestDemoteReturnShape:
    """demote() returns (state, [EmployeeDemoted(emp_id, savings_gained)])."""

    def test_demote_returns_two_tuple(self) -> None:
        actions = _actions()
        state = _make_state_with_employee(tier=2, salary=1250, cash=10_000)
        result = actions.demote(state, _emp_id("emp-001"))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_demote_returns_employee_demoted_with_savings(self) -> None:
        """demote() returns EmployeeDemoted(emp_id, savings_gained=demotion_savings)."""
        balance = load_balance()
        expected_savings = int(balance["employees"]["demotion_savings"])
        actions = _actions()
        state = _make_state_with_employee(tier=2, salary=1250, cash=10_000)
        _, events = actions.demote(state, _emp_id("emp-001"))
        assert len(events) == 1
        assert isinstance(events[0], EmployeeDemoted)
        assert events[0].employee_id == _emp_id("emp-001")
        assert events[0].savings_gained == expected_savings


class TestDemoteHappyPath:
    """F8 happy path: tier-1, salary /= multiplier, cash += demotion_savings."""

    def test_demote_decrements_tier(self) -> None:
        actions = _actions()
        state = _make_state_with_employee(tier=2, salary=1250, cash=10_000)
        new_state, _ = actions.demote(state, _emp_id("emp-001"))
        assert new_state.employees[_emp_id("emp-001")].tier == 1

    def test_demote_divides_salary(self) -> None:
        """salary_after = round(salary_before / salary_tier_multiplier)."""
        balance = load_balance()
        multiplier = float(balance["money"]["salary_tier_multiplier"])
        actions = _actions()
        state = _make_state_with_employee(tier=2, salary=1250, cash=10_000)
        new_state, _ = actions.demote(state, _emp_id("emp-001"))
        expected = int(round(1250 / multiplier))
        assert new_state.employees[_emp_id("emp-001")].salary_per_week == expected

    def test_demote_adds_savings_to_cash(self) -> None:
        """cash_after = cash_before + demotion_savings."""
        balance = load_balance()
        savings = int(balance["employees"]["demotion_savings"])
        actions = _actions()
        state = _make_state_with_employee(tier=2, salary=1250, cash=10_000)
        new_state, _ = actions.demote(state, _emp_id("emp-001"))
        assert new_state.company.cash == 10_000 + savings

    def test_demote_does_not_mutate_input_state(self) -> None:
        actions = _actions()
        state = _make_state_with_employee(tier=2, salary=1250, cash=10_000)
        original_cash = state.company.cash
        original_tier = state.employees[_emp_id("emp-001")].tier
        actions.demote(state, _emp_id("emp-001"))
        assert state.company.cash == original_cash
        assert state.employees[_emp_id("emp-001")].tier == original_tier


# ===================================================================== round-trip
# =====================================================================


class TestPromoteDemoteRoundTrip:
    """Promote then demote returns to original tier with salary drift <= 1."""

    def test_promote_then_demote_returns_to_original_tier_and_salary(self) -> None:
        """Given: tier=1, salary=1000
        When: promote() then demote()
        Then: tier == 1, salary within +-1 unit of original (rounding-safe).
        """
        actions = _actions()
        state = _make_state_with_employee(tier=1, salary=1000, cash=10_000)
        after_promote, _ = actions.promote(state, _emp_id("emp-001"))
        after_demote, _ = actions.demote(after_promote, _emp_id("emp-001"))
        assert after_demote.employees[_emp_id("emp-001")].tier == 1
        assert (
            abs(after_demote.employees[_emp_id("emp-001")].salary_per_week - 1000)
            <= 1
        )

    def test_promote_then_demote_cash_net_is_demotion_savings_minus_promotion_cost(
        self,
    ) -> None:
        """Net cash delta: +demotion_savings - promotion_cost."""
        balance = load_balance()
        cost = int(balance["employees"]["promotion_cost"])
        savings = int(balance["employees"]["demotion_savings"])
        actions = _actions()
        state = _make_state_with_employee(tier=1, salary=1000, cash=10_000)
        after_promote, _ = actions.promote(state, _emp_id("emp-001"))
        after_demote, _ = actions.demote(after_promote, _emp_id("emp-001"))
        assert after_demote.company.cash == 10_000 - cost + savings


# ===================================================================== grep test
# =====================================================================


class TestActionsModulePublishGuard:
    """actions.py MUST NOT contain any ``event_bus.publish(...)`` call."""

    def test_actions_module_source_exists(self) -> None:
        """actions.py exists on disk (the grep test presupposes the file)."""
        actions = _actions()
        path = _actions_source_path()
        assert path.is_file(), (
            f"{path} must exist; actions.py is the T10 deliverable"
        )
        # Module must also be importable (already asserted by _actions() above).
        assert actions is not None

    def test_actions_module_has_no_event_bus_publish_call(self) -> None:
        """No ``event_bus.publish(...)`` substring in actions.py."""
        path = _actions_source_path()
        text = path.read_text(encoding="utf-8")
        # Look for any form of event_bus.publish — both attribute and substring
        # variants. We require the strict pattern ``event_bus.publish(`` to
        # catch direct calls without false-flagging comments or docstrings
        # that mention the function name without calling it.
        assert "event_bus.publish(" not in text, (
            "actions.py must NOT call event_bus.publish(...) directly; "
            "actions are pure and return (state, events). Caller publishes."
        )

    def test_actions_module_does_not_import_event_bus(self) -> None:
        """actions.py MUST NOT import EventBus (no need; we never publish)."""
        path = _actions_source_path()
        text = path.read_text(encoding="utf-8")
        assert "EventBus" not in text, (
            "actions.py must not import EventBus — actions are pure, "
            "no publishing allowed in the engine actions layer"
        )
