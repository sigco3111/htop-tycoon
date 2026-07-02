"""T2.1 RED: compute_daily_progress + advance_projects."""

from __future__ import annotations

from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.enums import Department, Genre, Job, Platform
from htop_tycoon.domain.ids import EmployeeId, GameTitle, ProjectId
from htop_tycoon.domain.money import Money
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.quality import Progress, QualityAxes
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.domain.state import CompanyState
from htop_tycoon.engine.game_dev import (
    GENRE_FACTOR,
    advance_projects,
    compute_daily_progress,
)


def _emp(eid: int, **kwargs: object) -> Employee:
    defaults: dict[str, object] = {
        "id": EmployeeId(eid),
        "name": f"Emp{eid}",
        "job": Job.LEAD,
        "level": 5,
        "salary": Money(500_00),
        "satisfaction": 80,
        "dept": Department.DEV,
    }
    defaults.update(kwargs)
    return Employee(**defaults)  # type: ignore[arg-type]


def _project(**kwargs: object) -> GameProject:
    defaults: dict[str, object] = {
        "id": ProjectId(1),
        "title": GameTitle("Eldritch Quest"),
        "genre": Genre.RPG,
        "platform": Platform.PC,
        "console": None,
        "progress": Progress(0),
        "quality": QualityAxes(),
        "days_in_dev": 0,
        "lead_id": EmployeeId(1),
        "team_ids": (),
    }
    defaults.update(kwargs)
    return GameProject(**defaults)  # type: ignore[arg-type]


def test_genre_factor_table_complete() -> None:
    """Every Genre has a factor in [0.8, 1.2]."""
    assert set(GENRE_FACTOR.keys()) == set(Genre)
    for factor in GENRE_FACTOR.values():
        assert 0.8 <= factor <= 1.2


def test_compute_daily_progress_no_lead_returns_zero() -> None:
    state = CompanyState()
    proj = _project(lead_id=None)
    delta = compute_daily_progress(proj, state, GameRng(0))
    assert delta == 0


def test_compute_daily_progress_missing_employee_returns_zero() -> None:
    """Lead ID set but employee absent from state → delta=0."""
    state = CompanyState()  # no employees
    proj = _project(lead_id=EmployeeId(99))
    delta = compute_daily_progress(proj, state, GameRng(0))
    assert delta == 0


def test_compute_daily_progress_with_lead_positive() -> None:
    state = CompanyState().add_employee(_emp(1))
    proj = _project(lead_id=EmployeeId(1))
    delta = compute_daily_progress(proj, state, GameRng(0))
    assert delta > 0


def test_compute_daily_progress_team_bonus_capped_at_5() -> None:
    """Team of 5 vs team of 10 → same bonus (capped)."""
    rng_seed = 0
    state_small = CompanyState()
    for i in range(1, 6):
        state_small = state_small.add_employee(_emp(i))
    state_big = CompanyState()
    for i in range(1, 11):
        state_big = state_big.add_employee(_emp(i))

    proj_small = _project(team_ids=tuple(EmployeeId(i) for i in range(1, 6)))
    proj_big = _project(team_ids=tuple(EmployeeId(i) for i in range(1, 11)))

    delta_small = compute_daily_progress(proj_small, state_small, GameRng(rng_seed))
    delta_big = compute_daily_progress(proj_big, state_big, GameRng(rng_seed))
    # Both should hit the +50% cap (1 + 0.1 * 5 = 1.5).
    assert delta_small == delta_big
    assert delta_small > 0


def test_compute_daily_progress_genre_factor_applied() -> None:
    """ACTION genre (1.2) yields higher delta than PUZZLE (0.9) for same setup."""
    state = CompanyState().add_employee(_emp(1, satisfaction=100, level=10, job=Job.LEAD))
    proj_action = _project(genre=Genre.ACTION, lead_id=EmployeeId(1))
    proj_puzzle = _project(genre=Genre.PUZZLE, lead_id=EmployeeId(1))
    delta_action = compute_daily_progress(proj_action, state, GameRng(0))
    delta_puzzle = compute_daily_progress(proj_puzzle, state, GameRng(0))
    assert delta_action > delta_puzzle


def test_compute_daily_progress_deterministic() -> None:
    state = CompanyState().add_employee(_emp(1))
    proj = _project(lead_id=EmployeeId(1))
    a = compute_daily_progress(proj, state, GameRng(42))
    b = compute_daily_progress(proj, state, GameRng(42))
    assert a == b


def test_advance_projects_returns_new_state() -> None:
    state = CompanyState().add_project(_project())
    new_state = advance_projects(state, GameRng(0))
    assert new_state is not state


def test_advance_projects_increments_days_in_dev() -> None:
    state = (
        CompanyState()
        .add_employee(_emp(1))
        .add_project(_project(lead_id=EmployeeId(1)))
    )
    new_state = advance_projects(state, GameRng(0))
    assert new_state.projects[ProjectId(1)].days_in_dev == 1


def test_advance_projects_increments_progress() -> None:
    state = (
        CompanyState()
        .add_employee(_emp(1))
        .add_project(_project(lead_id=EmployeeId(1)))
    )
    new_state = advance_projects(state, GameRng(0))
    assert new_state.projects[ProjectId(1)].progress.value > 0


def test_advance_projects_does_not_mutate_input() -> None:
    state = (
        CompanyState()
        .add_employee(_emp(1))
        .add_project(_project(lead_id=EmployeeId(1)))
    )
    _ = advance_projects(state, GameRng(0))
    assert state.projects[ProjectId(1)].progress.value == 0
    assert state.projects[ProjectId(1)].days_in_dev == 0


def test_advance_projects_empty_state() -> None:
    """No projects → new state identical except no projects."""
    state = CompanyState()
    new_state = advance_projects(state, GameRng(0))
    assert new_state.projects == {}
