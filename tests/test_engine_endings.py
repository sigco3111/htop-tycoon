"""htop-tycoon v3.0 — engine.endings coverage tests. Spec §1.4.

Targets ``engine/endings.py`` (currently 67% covered) to push above 80%.
"""
from __future__ import annotations

from htop_tycoon.domain import (
    EndingKind,
    GameProject,
    GameState,
    GenreId,
    Platform,
    PlatformId,
    ProjectId,
    QualityAxis,
    ThemeId,
)
from htop_tycoon.engine.endings import check_endings

# --- helpers --------------------------------------------------------------


def _axes(avg: float) -> dict[QualityAxis, float]:
    return {axis: avg for axis in QualityAxis}


def _released(sales: int, avg: float = 5.0) -> GameProject:
    return GameProject(
        id=ProjectId("p"),
        name="Released",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=100.0,
        released_day=10,
        sales_total=sales,
        quality_axes=_axes(avg),
    )


def _state(*, cash: int = 100_000, projects=(), ending=None) -> GameState:
    return GameState(rng_seed=42, cash=cash, projects=projects, ending=ending)


# --- BANKRUPTCY ---------------------------------------------------------


def test_bankruptcy_fires_when_cash_below_threshold() -> None:
    """cash < -50_000 -> BANKRUPTCY event (priority 1)."""
    state = _state(cash=-50_001)
    event = check_endings(state)
    assert event is not None
    assert event.kind == "ending"
    assert event.payload["ending"] == EndingKind.BANKRUPTCY.name


def test_bankruptcy_does_not_fire_at_threshold_minus_one() -> None:
    """cash == -50_000 (the literal threshold) -> does NOT fire."""
    state = _state(cash=-50_000)
    assert check_endings(state) is None


def test_bankruptcy_does_not_fire_when_cash_positive() -> None:
    state = _state(cash=0)
    assert check_endings(state) is None


# --- MEGA_HIT -----------------------------------------------------------


def test_mega_hit_fires_when_project_sales_exceed_1m() -> None:
    """Any released project with sales_total >= 1_000_000 -> MEGA_HIT."""
    state = _state(projects=(_released(sales=1_000_000),))
    event = check_endings(state)
    assert event is not None
    assert event.payload["ending"] == EndingKind.MEGA_HIT.name


def test_mega_hit_does_not_fire_below_1m() -> None:
    state = _state(projects=(_released(sales=999_999),))
    assert check_endings(state) is None


def test_bankruptcy_takes_priority_over_mega_hit() -> None:
    """Spec §1.4: BANKRUPTCY (priority 100) > MEGA_HIT (priority 50)."""
    state = _state(
        cash=-100_000,
        projects=(_released(sales=2_000_000),),
    )
    event = check_endings(state)
    assert event is not None
    assert event.payload["ending"] == EndingKind.BANKRUPTCY.name


# --- HALL_OF_FAME -------------------------------------------------------


def test_hall_of_fame_fires_with_five_at_avg_8() -> None:
    """5 released projects, each at avg >= 8.0 -> HALL_OF_FAME."""
    projects = tuple(_released(sales=100, avg=8.0) for _ in range(5))
    state = _state(projects=projects)
    event = check_endings(state)
    assert event is not None
    assert event.payload["ending"] == EndingKind.HALL_OF_FAME.name


def test_hall_of_fame_does_not_fire_with_four() -> None:
    """4 released projects at avg 8.0 -> not enough (need 5)."""
    projects = tuple(_released(sales=100, avg=8.0) for _ in range(4))
    state = _state(projects=projects)
    assert check_endings(state) is None


def test_hall_of_fame_boundary_at_8_0_inclusive() -> None:
    """avg == 8.0 is exactly on the threshold (>= 8.0)."""
    projects = tuple(_released(sales=100, avg=8.0) for _ in range(5))
    state = _state(projects=projects)
    assert check_endings(state) is not None


def test_hall_of_fame_excludes_below_threshold() -> None:
    """5 released but one at avg 7.9 -> only 4 qualify -> no HoF."""
    projects = list(_released(sales=100, avg=8.0) for _ in range(4))
    projects.append(_released(sales=100, avg=7.9))
    state = _state(projects=tuple(projects))
    assert check_endings(state) is None


def test_mega_hit_takes_priority_over_hall_of_fame() -> None:
    """Spec §1.4: MEGA_HIT (50) > HALL_OF_FAME (40) when both qualify."""
    projects = list(_released(sales=1_000_000, avg=8.0) for _ in range(5))
    state = _state(projects=tuple(projects))
    event = check_endings(state)
    assert event is not None
    assert event.payload["ending"] == EndingKind.MEGA_HIT.name


# --- no re-fire after game ended ---------------------------------------


def test_no_refire_after_game_already_ended() -> None:
    """If state.ending is already set, check_endings returns None."""
    from htop_tycoon.domain import Ending

    state = _state(
        cash=-100_000,  # would normally fire BANKRUPTCY
        ending=Ending(kind=EndingKind.MEGA_HIT, day=1, cash_at_end=0, games_count=0),
    )
    assert check_endings(state) is None
