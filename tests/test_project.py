"""T2.2 RED: GameProject invariants."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.domain.enums import Console, Genre, Platform
from htop_tycoon.domain.ids import EmployeeId, GameTitle, ProjectId
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.quality import Progress, QualityAxes


def _basic(**kwargs: object) -> GameProject:
    defaults: dict[str, object] = {
        "id": ProjectId(1),
        "title": GameTitle("Eldritch Quest"),
        "genre": Genre.RPG,
        "platform": Platform.PC,
        "console": None,
        "progress": Progress(0),
        "quality": QualityAxes(),
        "days_in_dev": 0,
        "lead_id": None,
        "team_ids": (),
    }
    defaults.update(kwargs)
    return GameProject(**defaults)  # type: ignore[arg-type]


def test_project_minimal_construction() -> None:
    p = _basic()
    assert p.title == GameTitle("Eldritch Quest")
    assert p.progress.value == 0
    assert p.lead_id is None
    assert p.team_ids == ()


def test_project_progress_starts_at_zero() -> None:
    assert _basic().progress.value == 0


def test_project_advance_progress_normal() -> None:
    p = _basic(progress=Progress(50))
    advanced = p.advance(25)
    assert advanced.progress.value == 75


def test_project_advance_clamps_at_100() -> None:
    p = _basic(progress=Progress(80))
    advanced = p.advance(50)
    assert advanced.progress.value == 100


def test_project_advance_returns_new_instance() -> None:
    p = _basic(progress=Progress(50))
    advanced = p.advance(10)
    assert p.progress.value == 50
    assert advanced is not p


def test_project_is_shipped_when_progress_100() -> None:
    p = _basic(progress=Progress(100))
    assert p.is_shipped is True


def test_project_not_shipped_below_100() -> None:
    assert _basic(progress=Progress(99)).is_shipped is False
    assert _basic().is_shipped is False


def test_project_team_ids_normalized_to_tuple() -> None:
    """team_ids passed as list → stored as tuple for hashability."""
    p = _basic(team_ids=[EmployeeId(1), EmployeeId(2)])
    assert isinstance(p.team_ids, tuple)
    assert p.team_ids == (EmployeeId(1), EmployeeId(2))


def test_project_team_ids_already_tuple() -> None:
    p = _basic(team_ids=(EmployeeId(1),))
    assert isinstance(p.team_ids, tuple)


def test_project_assign_lead() -> None:
    p = _basic()
    with_lead = p.assign_lead(EmployeeId(7))
    assert with_lead.lead_id == EmployeeId(7)
    assert p.lead_id is None  # original unchanged


def test_project_add_team_member() -> None:
    p = _basic(team_ids=(EmployeeId(1),))
    with_member = p.add_team_member(EmployeeId(2))
    assert with_member.team_ids == (EmployeeId(1), EmployeeId(2))
    assert p.team_ids == (EmployeeId(1),)  # original unchanged


def test_project_add_duplicate_team_member_no_op() -> None:
    p = _basic(team_ids=(EmployeeId(1),))
    with_dup = p.add_team_member(EmployeeId(1))
    assert with_dup.team_ids == (EmployeeId(1),)


def test_project_frozen() -> None:
    p = _basic()
    with pytest.raises(FrozenInstanceError):
        p.title = GameTitle("Other")  # type: ignore[misc]


def test_project_default_console_field() -> None:
    """GameProject supports Platform.CONSOLE + specific Console hardware."""
    p = _basic(platform=Platform.CONSOLE, console=Console.NOVA)
    assert p.console == Console.NOVA
