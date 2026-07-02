"""HR module: hire/fire employees + candidate generation.

Phase 2I. Pure functions — no I/O. Wraps CompanyState with new employees
or removes them, plus a deterministic candidate generator for the
HireScreen modal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from htop_tycoon.domain import (
    CompanyState,
    Department,
    Employee,
    EmployeeId,
    Job,
    Money,
    compute_salary,
)

if TYPE_CHECKING:
    from htop_tycoon.domain.rng import GameRng


# Fixed name pool — 30 distinct English names for stable test output.
CANDIDATE_NAMES: tuple[str, ...] = (
    "Alex", "Blair", "Casey", "Dakota", "Ellis", "Finley", "Gray",
    "Harper", "Indigo", "Jordan", "Kai", "Lane", "Morgan", "Noor",
    "Oakley", "Parker", "Quinn", "Riley", "Sage", "Tatum",
    "Umi", "Vesper", "Wren", "Xen", "Yael", "Zion",
    "Avery", "Bryce", "Charlie", "Drew",
)


@dataclass(frozen=True, slots=True)
class HireCandidate:
    name: str
    job: Job
    suggested_level: int
    monthly_salary: Money
    department: Department


def _next_employee_id(state: CompanyState) -> EmployeeId:
    """Pick an EmployeeId that doesn't conflict with existing employees."""
    used = {int(eid) for eid in state.employees.keys()}
    candidate_id = 1
    while candidate_id in used:
        candidate_id += 1
    return EmployeeId(candidate_id)


def hire_employee(state: CompanyState, candidate: HireCandidate) -> CompanyState:
    """Add a new Employee to state with auto-assigned EmployeeId."""
    new_id = _next_employee_id(state)
    salary = candidate.monthly_salary
    new_emp = Employee(
        id=new_id,
        name=candidate.name,
        job=candidate.job,
        level=candidate.suggested_level,
        salary=salary,
        satisfaction=80,
        dept=candidate.department,
    )
    return state.add_employee(new_emp)


def fire_employee(state: CompanyState, employee_id: EmployeeId) -> CompanyState:
    """Remove an employee from state. No-op if id not found."""
    if employee_id not in state.employees:
        return state
    return state.remove_employee(employee_id)


def generate_candidates(
    rng: GameRng, count: int = 5, used_names: set[str] | None = None
) -> list[HireCandidate]:
    """Generate N random hire candidates, deterministic given rng seed.

    Names from CANDIDATE_NAMES pool, jobs from Job enum, levels 1-5.
    Department is sampled from a fixed distribution matching mock_state.
    """
    excluded = used_names or set()
    available = [n for n in CANDIDATE_NAMES if n not in excluded]
    if len(available) < count:
        # Fall back: cycle names if pool runs out (deterministic via rng)
        available = list(CANDIDATE_NAMES)
    rng.shuffle(available)
    picked_names = available[:count]

    jobs = tuple(Job)
    departments = (
        Department.DEV,
        Department.DEV,
        Department.ART,
        Department.SOUND,
        Department.QA,
    )

    candidates: list[HireCandidate] = []
    for name in picked_names:
        job = jobs[rng.int_range(0, len(jobs) - 1)]
        level = rng.int_range(1, 5)
        department = departments[rng.int_range(0, len(departments) - 1)]
        salary = compute_salary(job, level).amount
        candidates.append(
            HireCandidate(
                name=name,
                job=job,
                suggested_level=level,
                monthly_salary=salary,
                department=department,
            )
        )
    return candidates
