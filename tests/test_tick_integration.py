"""T6: tick integration — units_sold, counters, legacy recording."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Department,
    Employee,
    EmployeeId,
    GameProject,
    GameTitle,
    Genre,
    Job,
    Money,
    Platform,
    Progress,
    ProjectId,
    QualityAxes,
)
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine import tick


def _emp() -> Employee:
    return Employee(
        id=EmployeeId(1),
        name="Ada",
        job=Job.LEAD,
        level=5,
        salary=Money(880_00),
        satisfaction=85,
        dept=Department.DEV,
    )


def _project(pid: int = 1, **kwargs: object) -> GameProject:
    defaults: dict[str, object] = {
        "id": ProjectId(pid),
        "title": GameTitle("Eldritch Quest"),
        "genre": Genre.RPG,
        "platform": Platform.PC,
        "console": None,
        "progress": Progress(100),
        "quality": QualityAxes(80, 70, 60, 50),
        "days_in_dev": 100,
        "lead_id": None,
        "team_ids": (),
        "units_sold": 0,
        "hall_of_fame": False,
    }
    defaults.update(kwargs)
    return GameProject(**defaults)  # type: ignore[arg-type]


def test_tick_sets_units_sold_on_shipped_project() -> None:
    """A project reaching progress=100 in this tick gets units_sold computed."""
    state = CompanyState().add_project(_project())
    new_state = tick(state, GameRng(0))
    assert new_state.projects[ProjectId(1)].units_sold > 0


def test_tick_increments_games_shipped_when_project_ships() -> None:
    state = CompanyState().add_project(_project())
    new_state = tick(state, GameRng(0))
    assert new_state.games_shipped == 1


def test_tick_preserves_existing_units_sold_for_pre_shipped_projects() -> None:
    """Already-shipped projects (units_sold > 0) keep their units_sold value."""
    state = CompanyState().add_project(_project(units_sold=1_500_000))
    new_state = tick(state, GameRng(0))
    assert new_state.projects[ProjectId(1)].units_sold == 1_500_000


def test_tick_records_legacy_score_on_pre_shipped_mega_hit() -> None:
    """If a project ALREADY has 1M+ units_sold, ticking records MEGA_HIT legacy."""
    state = CompanyState().add_project(_project(units_sold=1_500_000))
    new_state = tick(state, GameRng(0))
    assert any(s.ending_kind.value == "MEGA_HIT" for s in new_state.legacy_scores)


def test_tick_records_legacy_only_once_for_same_kind() -> None:
    """Ticking twice should still produce a single MEGA_HIT legacy entry."""
    state = CompanyState().add_project(_project(units_sold=1_500_000))
    once = tick(state, GameRng(0))
    twice = tick(once, GameRng(0))
    mega_hits = [s for s in twice.legacy_scores if s.ending_kind.value == "MEGA_HIT"]
    assert len(mega_hits) == 1, "Idempotent per kind should prevent duplicates"


def test_tick_increments_mega_hits_when_pre_shipped_with_1M() -> None:
    state = CompanyState().add_project(_project(units_sold=1_500_000))
    new_state = tick(state, GameRng(0))
    assert new_state.mega_hits == 1


def test_tick_no_shipped_no_counters() -> None:
    state = CompanyState().add_employee(_emp())
    new_state = tick(state, GameRng(0))
    assert new_state.games_shipped == 0
    assert new_state.mega_hits == 0
    assert new_state.legacy_scores == ()
