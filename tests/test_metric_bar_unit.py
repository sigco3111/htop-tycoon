"""T2 RED: bar() helper + _pick_active_project."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    GameProject,
    GameTitle,
    Genre,
    Platform,
    Progress,
    ProjectId,
    QualityAxes,
)
from htop_tycoon.ui.widgets.metric_bar import (
    DEFAULT_BAR_WIDTH,
    EMPTY_CHAR,
    FILLED_CHAR,
    _pick_active_project,
    bar,
)


def test_bar_zero_returns_all_empty() -> None:
    assert bar(0) == EMPTY_CHAR * DEFAULT_BAR_WIDTH
    assert bar(0, 10) == "░" * 10


def test_bar_half_returns_half_filled() -> None:
    assert bar(50) == FILLED_CHAR * 5 + EMPTY_CHAR * 5


def test_bar_full_returns_all_filled() -> None:
    assert bar(100) == FILLED_CHAR * 10
    assert bar(100, 5) == FILLED_CHAR * 5


def test_bar_value_eighty() -> None:
    assert bar(80) == FILLED_CHAR * 8 + EMPTY_CHAR * 2


def test_bar_value_thirty_three() -> None:
    assert bar(33) == FILLED_CHAR * 3 + EMPTY_CHAR * 7


def test_bar_custom_width() -> None:
    assert bar(60, 5) == FILLED_CHAR * 3 + EMPTY_CHAR * 2


def test_pick_active_project_empty_returns_none() -> None:
    state = CompanyState()
    assert _pick_active_project(state) is None


def test_pick_active_project_single_returns_it() -> None:
    state = CompanyState().add_project(
        GameProject(
            id=ProjectId(1),
            title=GameTitle("X"),
            genre=Genre.RPG,
            platform=Platform.PC,
            console=None,
            progress=Progress(50),
            quality=QualityAxes(),
            days_in_dev=0,
            lead_id=None,
            team_ids=(),
        )
    )
    picked = _pick_active_project(state)
    assert picked is not None
    assert picked.id == ProjectId(1)


def test_pick_active_project_returns_lowest_progress() -> None:
    proj_high = GameProject(
        id=ProjectId(1),
        title=GameTitle("A"),
        genre=Genre.RPG,
        platform=Platform.PC,
        console=None,
        progress=Progress(90),
        quality=QualityAxes(),
        days_in_dev=0,
        lead_id=None,
        team_ids=(),
    )
    proj_low = GameProject(
        id=ProjectId(2),
        title=GameTitle("B"),
        genre=Genre.RPG,
        platform=Platform.PC,
        console=None,
        progress=Progress(10),
        quality=QualityAxes(),
        days_in_dev=0,
        lead_id=None,
        team_ids=(),
    )
    state = CompanyState().add_project(proj_high).add_project(proj_low)
    picked = _pick_active_project(state)
    assert picked is not None
    assert picked.id == ProjectId(2)


def test_bar_constants() -> None:
    assert FILLED_CHAR == "█"
    assert EMPTY_CHAR == "░"
    assert DEFAULT_BAR_WIDTH == 10
