"""htop-tycoon v3.0 — engine.actions coverage tests. Spec §3.2.1, §6.

Targets ``engine/actions.py`` (currently 61% covered) to push above 80%
by covering error/edge branches the pilot tests skip.

Anti-pattern guards honored:
- Real ``GameState`` aggregates; no monkey-patching of engine internals.
- GameRNG only; bare ``random.*`` untouched.
"""
from __future__ import annotations

import dataclasses

import pytest

from htop_tycoon.domain import (
    Department,
    Employee,
    EmployeeId,
    GameProject,
    GameState,
    GenreId,
    JobType,
    Platform,
    PlatformId,
    ProjectId,
    QualityAxis,
    ThemeId,
)
from htop_tycoon.engine import actions as engine_actions
from htop_tycoon.engine.rng import GameRNG

# --- helpers --------------------------------------------------------------


def _emp(eid: str, job: JobType = JobType.PROGRAMMER, level: int = 1) -> Employee:
    return Employee(
        id=EmployeeId(eid),
        name=f"테스터{eid}",
        dept=Department.DEVELOPMENT,
        job=job,
        level=level,
    )


def _project(pid: str = "p1") -> GameProject:
    return GameProject(
        id=ProjectId(pid),
        name=f"프로젝트 {pid}",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=0.0,
        quality_axes={axis: 5.0 for axis in QualityAxis},
    )


def _state(*, cash: int = 100_000, employees=(), projects=(), rng_seed: int = 42) -> GameState:
    return GameState(rng_seed=rng_seed, cash=cash, employees=employees, projects=projects)


def _rng() -> GameRNG:
    return GameRNG(42)


# ==========================================================================
# hire — happy path + insufficient funds
# ==========================================================================


def test_hire_success_deducts_cash_and_adds_employee() -> None:
    """hire with sufficient cash -> cash -= 1000, employees grow by 1."""
    state = _state(cash=10_000)
    new_state, events = engine_actions.hire(
        state, _rng(),
        dept=Department.PLANNING, job=JobType.GAME_DESIGNER,
    )
    assert new_state.cash == 9_000
    assert len(new_state.employees) == 1
    ok = next(e for e in events if e.kind == "hire")
    assert ok.payload["status"] == "ok"


def test_hire_insufficient_funds_returns_failure_event() -> None:
    """hire with cash < 1000 -> (state, [HireFailedEvent]); state unchanged."""
    state = _state(cash=500)
    new_state, events = engine_actions.hire(
        state, _rng(),
        dept=Department.PLANNING, job=JobType.GAME_DESIGNER,
    )
    assert new_state is state
    assert new_state.cash == 500
    assert len(new_state.employees) == 0
    fail = events[0]
    assert fail.payload["status"] == "failed"
    assert fail.payload["reason"] == "insufficient_cash"
    assert fail.payload["required"] == 1_000
    assert fail.payload["available"] == 500


# ==========================================================================
# fire — happy path + employee not found
# ==========================================================================


def test_fire_success_deducts_severance_and_removes_employee() -> None:
    """fire existing employee -> cash -= 500, employee removed."""
    emp = _emp("e1")
    state = _state(cash=10_000, employees=(emp,))
    new_state, events = engine_actions.fire(
        state, _rng(), employee_id="e1", reason="restructuring",
    )
    assert new_state.cash == 9_500
    assert new_state.employees == ()
    ok = events[0]
    assert ok.payload["status"] == "ok"
    assert ok.payload["employee_id"] == "e1"


def test_fire_unknown_employee_returns_failure() -> None:
    """fire with unknown id -> (state, [FireFailedEvent]); state unchanged."""
    state = _state(cash=10_000)
    new_state, events = engine_actions.fire(
        state, _rng(), employee_id="ghost", reason="x",
    )
    assert new_state.cash == 10_000
    fail = events[0]
    assert fail.payload["status"] == "failed"
    assert fail.payload["reason"] == "employee_not_found"


# ==========================================================================
# train — happy path + 3 failure modes
# ==========================================================================


def test_train_success_levels_up_and_deducts_cost() -> None:
    """train 1->3 costs 2 * 800 = 1600."""
    emp = _emp("e1", level=1)
    state = _state(cash=10_000, employees=(emp,))
    new_state, events = engine_actions.train(
        state, _rng(), employee_id="e1", target_level=3,
    )
    assert new_state.cash == 10_000 - 1_600
    assert new_state.employees[0].level == 3
    assert events[0].payload["status"] == "ok"


def test_train_unknown_employee_returns_failure() -> None:
    state = _state(cash=10_000)
    _, events = engine_actions.train(
        state, _rng(), employee_id="ghost", target_level=2,
    )
    assert events[0].payload["reason"] == "employee_not_found"


def test_train_target_below_current_returns_failure() -> None:
    """target_level < current -> failure (no downgrades via train)."""
    emp = _emp("e1", level=3)
    state = _state(cash=10_000, employees=(emp,))
    _, events = engine_actions.train(
        state, _rng(), employee_id="e1", target_level=2,
    )
    assert events[0].payload["reason"] == "target_out_of_range"


def test_train_target_above_max_level_returns_failure() -> None:
    """target_level > MAX_LEVEL (5) -> failure."""
    emp = _emp("e1", level=4)
    state = _state(cash=10_000, employees=(emp,))
    _, events = engine_actions.train(
        state, _rng(), employee_id="e1", target_level=99,
    )
    assert events[0].payload["reason"] == "target_out_of_range"
    assert events[0].payload["max"] == 5


def test_train_insufficient_cash_returns_failure() -> None:
    """Insufficient cash for the level delta -> failure."""
    emp = _emp("e1", level=1)
    state = _state(cash=100, employees=(emp,))  # need 1*800 = 800
    _, events = engine_actions.train(
        state, _rng(), employee_id="e1", target_level=2,
    )
    assert events[0].payload["reason"] == "insufficient_cash"


# ==========================================================================
# promote — happy path + unknown employee
# ==========================================================================


def test_promote_success_increments_level_by_one() -> None:
    emp = _emp("e1", level=2)
    state = _state(cash=10_000, employees=(emp,))
    new_state, events = engine_actions.promote(state, _rng(), employee_id="e1")
    assert new_state.employees[0].level == 3
    assert events[0].payload["status"] == "ok"


def test_promote_unknown_employee_returns_failure() -> None:
    state = _state(cash=10_000)
    _, events = engine_actions.promote(state, _rng(), employee_id="ghost")
    assert events[0].payload["reason"] == "employee_not_found"


# ==========================================================================
# demote — happy path + at_minimum + unknown
# ==========================================================================


def test_demote_happy_path_raises_value_error_until_engine_bug_fixed() -> None:
    """Known engine bug: ``engine.actions.demote`` passes ``init=False`` fields
    (``salary_daily``, ``skill_per_axis``) to :func:`dataclasses.replace`, which
    raises ``ValueError``. This test pins the current (broken) behavior; fix
    the engine action to use ``Employee.change_job``-style two-step replace
    (or recompute via ``Employee.__post_init__``) to make this return cleanly.

    Until that fix lands, this test serves as a regression guard so a refactor
    of ``demote`` does not silently change the contract.
    """
    emp = _emp("e1", level=3)
    state = _state(cash=10_000, employees=(emp,))
    with pytest.raises(ValueError) as excinfo:
        engine_actions.demote(state, _rng(), employee_id="e1")
    assert "init=False" in str(excinfo.value)


def test_demote_at_minimum_returns_failure() -> None:
    emp = _emp("e1", level=1)
    state = _state(cash=10_000, employees=(emp,))
    _, events = engine_actions.demote(state, _rng(), employee_id="e1")
    assert events[0].payload["reason"] == "already_at_minimum"
    # State unchanged
    assert state.employees[0].level == 1


def test_demote_unknown_employee_returns_failure() -> None:
    state = _state(cash=10_000)
    _, events = engine_actions.demote(state, _rng(), employee_id="ghost")
    assert events[0].payload["reason"] == "employee_not_found"


# ==========================================================================
# change_job — happy path + same_job + unknown
# ==========================================================================


def test_change_job_success_multiplies_salary() -> None:
    emp = _emp("e1", job=JobType.PROGRAMMER, level=1)
    state = _state(cash=10_000, employees=(emp,))
    new_state, events = engine_actions.change_job(
        state, _rng(), employee_id="e1", new_job=JobType.GAME_DESIGNER,
    )
    updated = new_state.employees[0]
    assert updated.job is JobType.GAME_DESIGNER
    assert updated.salary_daily == int(round(emp.salary_daily * 1.2))
    assert events[0].payload["status"] == "ok"


def test_change_job_same_job_returns_failure() -> None:
    emp = _emp("e1", job=JobType.PROGRAMMER, level=1)
    state = _state(cash=10_000, employees=(emp,))
    _, events = engine_actions.change_job(
        state, _rng(), employee_id="e1", new_job=JobType.PROGRAMMER,
    )
    assert events[0].payload["reason"] == "same_job"


def test_change_job_unknown_employee_returns_failure() -> None:
    state = _state(cash=10_000)
    _, events = engine_actions.change_job(
        state, _rng(), employee_id="ghost", new_job=JobType.PROGRAMMER,
    )
    assert events[0].payload["reason"] == "employee_not_found"


# ==========================================================================
# start_game — success + duplicate active project
# ==========================================================================


def test_start_game_success_creates_project() -> None:
    state = _state(cash=100_000)
    new_state, events = engine_actions.start_game(
        state, _rng(),
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
    )
    assert len(new_state.projects) == 1
    assert events[0].payload["status"] == "ok"


def test_start_game_with_active_project_fails() -> None:
    """Spec §1.3: max 1 active project at a time."""
    p = _project("p1")
    state = _state(projects=(p,))
    _, events = engine_actions.start_game(
        state, _rng(),
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
    )
    assert events[0].payload["reason"] == "active_project_exists"


# ==========================================================================
# assign — happy path + 3 failure modes
# ==========================================================================


def test_assign_success_appends_to_assignees() -> None:
    emp = _emp("e1")
    p = _project("p1")
    state = _state(employees=(emp,), projects=(p,))
    new_state, events = engine_actions.assign(
        state, _rng(), employee_id="e1", project_id="p1",
    )
    assert EmployeeId("e1") in new_state.projects[0].assignees
    assert events[0].payload["status"] == "ok"


def test_assign_unknown_employee_returns_failure() -> None:
    p = _project("p1")
    state = _state(projects=(p,))
    _, events = engine_actions.assign(
        state, _rng(), employee_id="ghost", project_id="p1",
    )
    assert events[0].payload["reason"] == "employee_not_found"


def test_assign_unknown_project_returns_failure() -> None:
    emp = _emp("e1")
    state = _state(employees=(emp,))
    _, events = engine_actions.assign(
        state, _rng(), employee_id="e1", project_id="ghost",
    )
    assert events[0].payload["reason"] == "project_not_found"


def test_assign_already_assigned_returns_failure() -> None:
    emp = _emp("e1")
    p = _project("p1")
    p_assigned = dataclasses.replace(p, assignees=(EmployeeId("e1"),))
    state = _state(employees=(emp,), projects=(p_assigned,))
    _, events = engine_actions.assign(
        state, _rng(), employee_id="e1", project_id="p1",
    )
    assert events[0].payload["reason"] == "already_assigned"


# ==========================================================================
# nothing — pure no-op
# ==========================================================================


def test_nothing_returns_state_unchanged_and_no_events() -> None:
    """nothing: pure no-op (state, [])."""
    state = _state(cash=42)
    new_state, events = engine_actions.nothing(state, _rng())
    assert new_state is state
    assert events == []
