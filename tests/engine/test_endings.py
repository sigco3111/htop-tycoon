"""T4: detect_ending rules + record_ending idempotency."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Console,
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
from htop_tycoon.engine.endings import (
    BANKRUPTCY_THRESHOLD_CENTS,
    MEGA_HIT_UNITS,
    EndingKind,
    construct_legacy_score,
    detect_ending,
    record_ending,
)


def _emp(eid: int = 1) -> Employee:
    return Employee(
        id=EmployeeId(eid),
        name="Ada",
        job=Job.LEAD,
        level=5,
        salary=Money(0),
        satisfaction=85,
        dept=Department.DEV,
    )


def _project(pid: int = 1, **kwargs: object) -> GameProject:
    defaults: dict[str, object] = {
        "id": ProjectId(pid),
        "title": GameTitle("X"),
        "genre": Genre.RPG,
        "platform": Platform.PC,
        "console": None,
        "progress": Progress(0),
        "quality": QualityAxes(60, 40, 30, 50),
        "days_in_dev": 0,
        "lead_id": None,
        "team_ids": (),
        "units_sold": 0,
        "hall_of_fame": False,
    }
    defaults.update(kwargs)
    return GameProject(**defaults)  # type: ignore[arg-type]


def test_detect_ending_returns_none_for_normal_state() -> None:
    state = CompanyState().add_employee(_emp()).add_project(_project())
    assert detect_ending(state) is None


def test_detect_ending_returns_bankruptcy_when_cash_below_threshold() -> None:
    state = CompanyState(cash=Money(BANKRUPTCY_THRESHOLD_CENTS - 100))
    ending = detect_ending(state)
    assert ending is not None
    assert ending.kind == EndingKind.BANKRUPTCY


def test_detect_ending_bankruptcy_threshold_is_strict_less_than() -> None:
    """Cash exactly at threshold should NOT trigger bankruptcy."""
    state = CompanyState(cash=Money(BANKRUPTCY_THRESHOLD_CENTS))
    assert detect_ending(state) is None


def test_detect_ending_returns_voluntary_sale_when_pending_and_cash_ok() -> None:
    state = (
        CompanyState(cash=Money(200_000_00))
        .set_voluntary_sale_pending(True)
    )
    ending = detect_ending(state)
    assert ending is not None
    assert ending.kind == EndingKind.VOLUNTARY_SALE


def test_detect_ending_voluntary_sale_with_low_cash_returns_none() -> None:
    state = (
        CompanyState(cash=Money(150_000_00))
        .set_voluntary_sale_pending(True)
    )
    assert detect_ending(state) is None


def test_detect_ending_priority_bankruptcy_beats_voluntary_sale() -> None:
    state = (
        CompanyState(cash=Money(BANKRUPTCY_THRESHOLD_CENTS - 100))
        .set_voluntary_sale_pending(True)
    )
    ending = detect_ending(state)
    assert ending is not None
    assert ending.kind == EndingKind.BANKRUPTCY


def test_detect_ending_returns_mega_hit_when_project_units_exceed_1M() -> None:
    state = CompanyState().add_project(_project(units_sold=MEGA_HIT_UNITS + 1))
    ending = detect_ending(state)
    assert ending is not None
    assert ending.kind == EndingKind.MEGA_HIT


def test_detect_ending_returns_hall_of_fame_when_five_games_flagged() -> None:
    state = CompanyState()
    for i in range(1, 6):
        state = state.add_project(_project(pid=i, hall_of_fame=True))
    ending = detect_ending(state)
    assert ending is not None
    assert ending.kind == EndingKind.HALL_OF_FAME


def test_detect_ending_returns_secret_when_own_console_and_million_units_on_it() -> None:
    state = (
        CompanyState()
        .mark_own_console(Console.NOVA)
        .add_project(_project(platform=Platform.CONSOLE, console=Console.NOVA, units_sold=MEGA_HIT_UNITS + 1))
    )
    ending = detect_ending(state)
    assert ending is not None
    assert ending.kind == EndingKind.SECRET


def test_detect_ending_secret_requires_units_on_own_console() -> None:
    state = (
        CompanyState()
        .mark_own_console(Console.NOVA)
        .add_project(_project(units_sold=MEGA_HIT_UNITS + 1))
    )
    ending = detect_ending(state)
    assert ending is not None
    assert ending.kind != EndingKind.SECRET
    assert ending.kind == EndingKind.MEGA_HIT


def test_record_ending_appends_to_legacy_scores_tuple() -> None:
    state = CompanyState().add_project(_project(units_sold=MEGA_HIT_UNITS + 1))
    ending = detect_ending(state)
    assert ending is not None
    new_state = record_ending(state, ending)
    assert len(new_state.legacy_scores) == 1
    assert new_state.legacy_scores[0].ending_kind == EndingKind.MEGA_HIT


def test_record_ending_is_idempotent_per_kind() -> None:
    state = CompanyState().add_project(_project(units_sold=MEGA_HIT_UNITS + 1))
    ending = detect_ending(state)
    assert ending is not None
    once = record_ending(state, ending)
    twice = record_ending(once, ending)
    assert len(twice.legacy_scores) == 1, "Same kind should not double-record"


def test_construct_legacy_score_captures_state_snapshot() -> None:
    state = CompanyState(cash=Money(150_000_00), fans=1234)
    ending = detect_ending(state)
    assert ending is None  # no ending triggers here, but construct_legacy_score takes any ending
    from htop_tycoon.engine.endings import Ending
    fake_ending = Ending(kind=EndingKind.MEGA_HIT, triggered_at=(2, 50), description="x")
    score = construct_legacy_score(state, fake_ending)
    assert score.ending_kind == EndingKind.MEGA_HIT
    assert score.ending_year == 2
    assert score.ending_cash_cents == 150_000_00
    assert score.total_fans == 1234


def test_increment_helpers_work() -> None:
    state = CompanyState()
    assert state.games_shipped == 0
    assert state.mega_hits == 0
    state = state.increment_games_shipped().increment_mega_hits()
    assert state.games_shipped == 1
    assert state.mega_hits == 1
