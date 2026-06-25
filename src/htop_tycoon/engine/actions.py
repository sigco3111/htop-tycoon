"""Engine: pure employee actions (T10) — hire / fire / promote / demote.

Per ``.omo/plans/htop-tycoon.md`` line 332-346, every action is a PURE
function returning ``(new_state, list[Event])``. Actions NEVER call
``event_bus.publish``; the caller (T9 tick engine or T16 App) publishes.
Numeric constants (severance, promotion cost, savings, salary) are read
from ``balance.yaml`` — never hardcoded in this module.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from htop_tycoon.data import load_balance
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.state import DepartmentId, EmployeeId, GameState
from htop_tycoon.engine.events import (
    AlertRaised,
    EmployeeDemoted,
    EmployeeFired,
    EmployeeHired,
    EmployeePromoted,
    Event,
)
from htop_tycoon.engine.names import generate_korean_name
from htop_tycoon.engine.rng import GameRNG

__all__ = ["demote", "fire", "hire", "promote"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _new_employee_id(rng: GameRNG) -> EmployeeId:
    """``"emp_{n:08d}"`` where n = ``rng.int(0, 1_000_000_000)``."""
    n = rng.int(0, 1_000_000_000)
    return EmployeeId(f"emp_{n:08d}")


def _require_department(state: GameState, dept_id: DepartmentId) -> None:
    """Raise ``ValueError`` if ``dept_id`` is not in ``state.departments``."""
    if dept_id not in state.departments:
        raise ValueError(f"unknown department id: {dept_id!r}")


def _require_employee(state: GameState, employee_id: EmployeeId) -> Employee:
    """Return the employee or raise ``KeyError``.

    ``GameState.employees`` is typed ``dict[EmployeeId, Any]`` to avoid a
    circular import; the cast narrows back to ``Employee`` at the boundary.
    """
    if employee_id not in state.employees:
        raise KeyError(f"unknown employee id: {employee_id!r}")
    return cast(Employee, state.employees[employee_id])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def hire(
    state: GameState,
    dept_id: DepartmentId,
    rng: GameRNG,
) -> tuple[GameState, list[Event]]:
    """Hire a new employee into ``dept_id``.

    Returns a NEW state with one more employee, the dept roster augmented
    by the new id, and ``dept.head_employee_id`` set to the new hire when
    the dept previously had no head. Returns ``[EmployeeHired(new_id)]``.

    New-employee attributes (deterministic from ``rng`` + ``balance.yaml``):
    name via ``generate_korean_name``; id via ``_new_employee_id``;
    skill in ``employees.starting_skill_range``; tier=1; salary from
    ``employees.starting_salary_per_week``; satisfaction=60;
    hired_tick = ``state.tick``.

    Raises:
        ValueError: if ``dept_id`` is not in ``state.departments``.
    """
    _require_department(state, dept_id)
    balance = load_balance()

    skill_lo, skill_hi = balance["employees"]["starting_skill_range"]
    starting_salary = int(balance["employees"]["starting_salary_per_week"])

    new_id = _new_employee_id(rng)
    new_employee = Employee(
        id=new_id,
        name=generate_korean_name(rng),
        dept_id=dept_id,
        skill=rng.int(int(skill_lo), int(skill_hi)),
        tier=1,
        salary_per_week=starting_salary,
        satisfaction=60,
        hired_tick=state.tick,
    )

    dept = state.departments[dept_id]
    new_dept = dataclasses.replace(
        dept,
        employee_ids=[*dept.employee_ids, new_id],
        head_employee_id=(
            new_id if dept.head_employee_id is None else dept.head_employee_id
        ),
    )
    new_state = dataclasses.replace(
        state,
        departments={**state.departments, dept_id: new_dept},
        employees={**state.employees, new_id: new_employee},
    )
    return new_state, [EmployeeHired(employee_id=new_id)]


def fire(
    state: GameState,
    employee_id: EmployeeId,
    rng: GameRNG | None = None,  # noqa: ARG001 — reserved for future variance
) -> tuple[GameState, list[Event]]:
    """Fire ``employee_id``, paying ``fire_severance_per_tier * tier`` out of cash.

    Returns a NEW state with the employee removed from ``state.employees``
    AND from the dept's roster; the dept's ``head_employee_id`` is cleared
    when the fired employee was the head. Returns
    ``[EmployeeFired(employee_id, severance_paid)]``.

    No skill protection: even max-skill employees are fired on call.
    Cash may go negative (matches ``Company.cash`` debt semantics).

    The ``rng`` argument is accepted to match the locked signature; it is
    currently unused.

    Raises:
        KeyError: if ``employee_id`` is not in ``state.employees``.
    """
    balance = load_balance()
    per_tier = int(balance["money"]["fire_severance_per_tier"])

    employee = _require_employee(state, employee_id)
    severance_paid = per_tier * employee.tier

    new_company = dataclasses.replace(
        state.company,
        cash=state.company.cash - severance_paid,
    )
    dept = state.departments[employee.dept_id]
    new_dept = dataclasses.replace(
        dept,
        employee_ids=[eid for eid in dept.employee_ids if eid != employee_id],
        head_employee_id=(
            None
            if dept.head_employee_id == employee_id
            else dept.head_employee_id
        ),
    )
    new_state = dataclasses.replace(
        state,
        company=new_company,
        departments={**state.departments, employee.dept_id: new_dept},
        employees={
            eid: emp for eid, emp in state.employees.items() if eid != employee_id
        },
    )
    return new_state, [
        EmployeeFired(employee_id=employee_id, severance_paid=severance_paid)
    ]


def promote(
    state: GameState,
    employee_id: EmployeeId,
) -> tuple[GameState, list[Event]]:
    """Promote (F7): tier+1, salary *= multiplier, cash -= promotion_cost.

    Returns a NEW state on success with the employee at tier+1,
    salary = ``round(salary * salary_tier_multiplier)``, and cash
    decreased by ``promotion_cost``. Returns ``[EmployeePromoted(emp_id)]``.

    Budget rejection: when ``cash < promotion_cost``, returns the SAME
    state object (no replace) and ``[AlertRaised("예산 부족 — 승진 불가",
    "warn")]`` so the UI can react without committing a state change.

    Raises:
        KeyError: if ``employee_id`` is not in ``state.employees``.
        ValueError: if the employee is already at tier 5 (raised by
            ``Employee.promote()``).
    """
    balance = load_balance()
    cost = int(balance["employees"]["promotion_cost"])

    if state.company.cash < cost:
        return state, [
            AlertRaised(message_ko="예산 부족 — 승진 불가", severity="warn")
        ]

    employee = _require_employee(state, employee_id)
    new_employee = employee.promote()  # raises if at TIER_MAX
    new_company = dataclasses.replace(
        state.company,
        cash=state.company.cash - cost,
    )
    new_state = dataclasses.replace(
        state,
        company=new_company,
        employees={**state.employees, employee_id: new_employee},
    )
    return new_state, [EmployeePromoted(employee_id=employee_id)]


def demote(
    state: GameState,
    employee_id: EmployeeId,
) -> tuple[GameState, list[Event]]:
    """Demote (F8): tier-1 (floored at 1), salary /= multiplier, cash += savings.

    When tier > 1: returns a NEW state with the employee at tier-1,
    salary = ``round(salary / salary_tier_multiplier)``, and cash
    increased by ``demotion_savings``. Returns
    ``[EmployeeDemoted(emp_id, savings_gained=demotion_savings)]``.

    Floor case (tier == 1): returns the SAME state object and
    ``[EmployeeDemoted(emp_id, savings_gained=0)]`` — the 0-savings event
    signals "attempted but no-op" so the UI can still refresh.

    Raises:
        KeyError: if ``employee_id`` is not in ``state.employees``.
    """
    balance = load_balance()
    savings = int(balance["employees"]["demotion_savings"])

    employee = _require_employee(state, employee_id)

    if employee.tier <= 1:
        return state, [
            EmployeeDemoted(employee_id=employee_id, savings_gained=0)
        ]

    new_employee = employee.demote()
    new_company = dataclasses.replace(
        state.company,
        cash=state.company.cash + savings,
    )
    new_state = dataclasses.replace(
        state,
        company=new_company,
        employees={**state.employees, employee_id: new_employee},
    )
    return new_state, [
        EmployeeDemoted(employee_id=employee_id, savings_gained=savings)
    ]
