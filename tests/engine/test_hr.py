"""Phase 2I: HR — hire/fire employees + candidate generation."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Department,
    Employee,
    EmployeeId,
    Job,
    Money,
)
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine.hr import (
    CANDIDATE_NAMES,
    HireCandidate,
    fire_employee,
    generate_candidates,
    hire_employee,
)


def _emp(eid: int, name: str = "Existing") -> Employee:
    return Employee(
        id=EmployeeId(eid),
        name=name,
        job=Job.JUNIOR,
        level=1,
        salary=Money(200_00),
        satisfaction=80,
        dept=Department.DEV,
    )


def test_generate_candidates_returns_count() -> None:
    candidates = generate_candidates(GameRng(0), count=5)
    assert len(candidates) == 5


def test_generate_candidates_deterministic() -> None:
    a = generate_candidates(GameRng(42), count=5)
    b = generate_candidates(GameRng(42), count=5)
    assert [(c.name, c.job, c.suggested_level) for c in a] == [
        (c.name, c.job, c.suggested_level) for c in b
    ]


def test_generate_candidates_unique_names() -> None:
    candidates = generate_candidates(GameRng(7), count=10)
    names = [c.name for c in candidates]
    assert len(set(names)) == len(names), "Names should be unique"


def test_generate_candidates_excludes_used() -> None:
    used = {"Alex", "Blair", "Casey"}
    candidates = generate_candidates(GameRng(0), count=5, used_names=used)
    for c in candidates:
        assert c.name not in used


def test_generate_candidates_level_in_range() -> None:
    candidates = generate_candidates(GameRng(0), count=10)
    for c in candidates:
        assert 1 <= c.suggested_level <= 5


def test_generate_candidates_salary_matches_compute() -> None:
    """Salary should match compute_salary(job, level)."""
    from htop_tycoon.domain import compute_salary

    candidates = generate_candidates(GameRng(0), count=10)
    for c in candidates:
        assert c.monthly_salary == compute_salary(c.job, c.suggested_level).amount


def test_hire_employee_adds_with_auto_id() -> None:
    state = CompanyState()
    candidate = HireCandidate(
        name="Alex", job=Job.LEAD, suggested_level=3,
        monthly_salary=Money(400_00), department=Department.DEV,
    )
    new_state = hire_employee(state, candidate)
    assert len(new_state.employees) == 1
    emp = next(iter(new_state.employees.values()))
    assert emp.name == "Alex"
    assert emp.job == Job.LEAD
    assert emp.satisfaction == 80


def test_hire_employee_does_not_mutate_input() -> None:
    state = CompanyState()
    candidate = HireCandidate(
        name="Alex", job=Job.LEAD, suggested_level=3,
        monthly_salary=Money(400_00), department=Department.DEV,
    )
    _ = hire_employee(state, candidate)
    assert len(state.employees) == 0


def test_hire_employee_picks_unique_id() -> None:
    state = CompanyState().add_employee(_emp(1)).add_employee(_emp(2))
    candidate = HireCandidate(
        name="Alex", job=Job.JUNIOR, suggested_level=1,
        monthly_salary=Money(200_00), department=Department.QA,
    )
    new_state = hire_employee(state, candidate)
    new_ids = {int(eid) for eid in new_state.employees.keys()}
    assert 3 in new_ids  # auto-assigned next ID
    assert len(new_ids) == 3


def test_fire_employee_removes() -> None:
    state = CompanyState().add_employee(_emp(1))
    new_state = fire_employee(state, EmployeeId(1))
    assert len(new_state.employees) == 0


def test_fire_employee_missing_id_is_noop() -> None:
    state = CompanyState().add_employee(_emp(1))
    new_state = fire_employee(state, EmployeeId(99))
    assert len(new_state.employees) == 1


def test_candidate_names_pool_size_30() -> None:
    assert len(CANDIDATE_NAMES) >= 30
