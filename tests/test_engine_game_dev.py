"""htop-tycoon v3.0 — engine.game_dev coverage tests. Spec §2.2.

Targets ``engine/game_dev.py`` (currently 42% covered) to push above 80%.

Verifies:
- ``advance_projects`` advances progress by summing employee FUN-axis skills.
- Unassigned projects (zombie games per spec §1.3) make no progress.
- ``is_project_complete`` wraps the property.
- Milestone events fire at 25/50/75% thresholds and support skip-over.
- Complete projects pass through unchanged.
- Empty state is a clean no-op.
"""
from __future__ import annotations

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
from htop_tycoon.engine.game_dev import advance_projects, is_project_complete

# --- helpers --------------------------------------------------------------


def _make_employee(eid: str, job: JobType = JobType.PROGRAMMER, level: int = 1) -> Employee:
    """Construct an Employee with deterministic id."""
    return Employee(
        id=EmployeeId(eid),
        name=f"테스터{eid}",
        dept=Department.DEVELOPMENT,
        job=job,
        level=level,
    )


def _make_project(
    pid: str,
    *,
    progress: float = 0.0,
    assignees: tuple[str, ...] = (),
    released_day: int | None = None,
) -> GameProject:
    return GameProject(
        id=ProjectId(pid),
        name=f"프로젝트 {pid}",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=progress,
        assignees=tuple(EmployeeId(a) for a in assignees),
        released_day=released_day,
        quality_axes={axis: 5.0 for axis in QualityAxis},
    )


# --- is_project_complete --------------------------------------------------


def test_is_project_complete_true_when_progress_100() -> None:
    """A project at 100% progress is complete."""
    p = _make_project("p1", progress=100.0)
    assert is_project_complete(p) is True


def test_is_project_complete_false_when_below_100() -> None:
    """A project below 100% is not complete."""
    p = _make_project("p1", progress=99.9)
    assert is_project_complete(p) is False


# --- advance_projects: empty / no-op ------------------------------------


def test_advance_projects_no_projects_no_op() -> None:
    """Empty state -> (state, []): no events, no changes."""
    state = GameState(rng_seed=42, projects=())
    new_state, events = advance_projects(state)
    assert new_state.projects == state.projects
    assert events == []


def test_advance_projects_zombie_project_no_progress() -> None:
    """A project with no assignees (zombie) gains no progress and no events."""
    p = _make_project("zombie", progress=10.0, assignees=())
    state = GameState(rng_seed=42, projects=(p,))
    new_state, events = advance_projects(state)
    updated = new_state.projects[0]
    assert updated.progress_pct == 10.0
    assert events == []


def test_advance_projects_unknown_assignee_silently_skipped() -> None:
    """An assignee ID that no longer resolves to an employee is skipped
    (defensive: ASSIGN action could be in-flight across save/load)."""
    p = _make_project("p1", progress=0.0, assignees=("ghost",))
    state = GameState(rng_seed=42, projects=(p,), employees=())
    new_state, events = advance_projects(state)
    # Unknown assignee -> empty contributors -> 0 progress, no events.
    assert new_state.projects[0].progress_pct == 0.0
    assert events == []


# --- advance_projects: happy paths --------------------------------------


def test_advance_projects_sums_employee_fun_skills() -> None:
    """One day of advance = sum of assignees' FUN-axis skill_per_axis."""
    # Programmer L1 FUN skill = 2.0 (per _JOB_QUALITY_CONTRIBUTIONS × 1.0 mult)
    emp = _make_employee("e1", job=JobType.PROGRAMMER, level=1)
    p = _make_project("p1", progress=0.0, assignees=("e1",))
    state = GameState(rng_seed=42, projects=(p,), employees=(emp,))
    new_state, _ = advance_projects(state)
    assert new_state.projects[0].progress_pct == pytest.approx(2.0, abs=1e-9)


def test_advance_projects_multiple_assignees_accumulate() -> None:
    """Two programmers -> 2 × FUN skill contribution."""
    e1 = _make_employee("e1", job=JobType.PROGRAMMER, level=1)
    e2 = _make_employee("e2", job=JobType.PROGRAMMER, level=1)
    p = _make_project("p1", progress=0.0, assignees=("e1", "e2"))
    state = GameState(rng_seed=42, projects=(p,), employees=(e1, e2))
    new_state, _ = advance_projects(state)
    assert new_state.projects[0].progress_pct == pytest.approx(4.0, abs=1e-9)


# --- milestones ----------------------------------------------------------


def test_advance_projects_emits_25_percent_milestone() -> None:
    """Crossing 25% emits one milestone event with payload ``milestone_pct``."""
    emp = _make_employee("e1", job=JobType.PROGRAMMER, level=1)
    # Start at 24.0; one tick adds 2.0 -> 26.0 -> crosses 25.
    p = _make_project("p1", progress=24.0, assignees=("e1",))
    state = GameState(rng_seed=42, projects=(p,), employees=(emp,))
    _, events = advance_projects(state)
    ms = [e for e in events if e.kind == "milestone"]
    assert len(ms) == 1
    assert ms[0].payload["milestone_pct"] == 25.0
    assert ms[0].payload["project_id"] == p.id


def test_advance_projects_emits_50_and_75_milestones() -> None:
    """Crossing both 50% and 75% in one tick emits two events."""
    emp_a = _make_employee("e1", job=JobType.PROGRAMMER, level=5)
    emp_b = _make_employee("e2", job=JobType.PROGRAMMER, level=5)
    emp_c = _make_employee("e3", job=JobType.PROGRAMMER, level=5)
    emp_d = _make_employee("e4", job=JobType.PROGRAMMER, level=5)
    emp_e = _make_employee("e5", job=JobType.PROGRAMMER, level=5)
    emp_f = _make_employee("e6", job=JobType.PROGRAMMER, level=5)
    emp_g = _make_employee("e7", job=JobType.PROGRAMMER, level=5)
    emp_h = _make_employee("e8", job=JobType.PROGRAMMER, level=5)
    emp_i = _make_employee("e9", job=JobType.PROGRAMMER, level=5)
    emp_j = _make_employee("e10", job=JobType.PROGRAMMER, level=5)
    # 10 L5 programmers = 10 * (2.0 * 1.8) = 36.0 / day
    p = _make_project("p1", progress=49.0, assignees=tuple(f"e{i}" for i in range(1, 11)))
    state = GameState(
        rng_seed=42,
        projects=(p,),
        employees=(emp_a, emp_b, emp_c, emp_d, emp_e,
                   emp_f, emp_g, emp_h, emp_i, emp_j),
    )
    _, events = advance_projects(state)
    crossed = sorted(e.payload["milestone_pct"] for e in events if e.kind == "milestone")
    assert crossed == [50.0, 75.0]


def test_advance_projects_no_milestone_emitted_below_first_threshold() -> None:
    """Progress that does not cross any threshold emits no milestones."""
    emp = _make_employee("e1", job=JobType.PROGRAMMER, level=1)
    p = _make_project("p1", progress=10.0, assignees=("e1",))
    state = GameState(rng_seed=42, projects=(p,), employees=(emp,))
    _, events = advance_projects(state)
    ms = [e for e in events if e.kind == "milestone"]
    assert ms == []


def test_advance_projects_does_not_re_emit_milestone() -> None:
    """A milestone already crossed in a prior tick is NOT re-emitted."""
    emp = _make_employee("e1", job=JobType.PROGRAMMER, level=1)
    p = _make_project("p1", progress=25.5, assignees=("e1",))  # past 25
    state = GameState(rng_seed=42, projects=(p,), employees=(emp,))
    _, events = advance_projects(state)
    # 25.5 + 2.0 = 27.5; 25.0 is NOT crossed (prev=25.5 >= 25.0).
    assert events == []


def test_advance_projects_complete_project_passes_through() -> None:
    """A complete project is passed through unchanged (no progress, no event)."""
    p = _make_project("p1", progress=100.0, released_day=1)
    state = GameState(rng_seed=42, projects=(p,))
    new_state, events = advance_projects(state)
    assert new_state.projects[0] is p
    assert events == []


def test_advance_projects_clamped_at_100() -> None:
    """A large skill contribution is clamped at progress_pct=100.0."""
    emp = _make_employee("e1", job=JobType.PROGRAMMER, level=5)
    p = _make_project("p1", progress=99.0, assignees=("e1",))
    state = GameState(rng_seed=42, projects=(p,), employees=(emp,))
    new_state, _ = advance_projects(state)
    # 3.6 + 99.0 = 102.6 -> clamped to 100.0
    assert new_state.projects[0].progress_pct == 100.0


# --- pytest import shim (used above for approx) -------------------------


import pytest  # noqa: E402  (kept at bottom for readability above)
