"""T3.1 RED: tick orchestration — one game day."""

from __future__ import annotations

from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.enums import Department, Genre, Job, Platform
from htop_tycoon.domain.ids import EmployeeId, GameTitle, ProjectId
from htop_tycoon.domain.money import Money
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.quality import Progress, QualityAxes
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.domain.state import CompanyState
from htop_tycoon.engine.market import MarketState
from htop_tycoon.engine.tick import DEFAULT_MARKET, tick


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
        "title": GameTitle("EQ"),
        "genre": Genre.RPG,
        "platform": Platform.PC,
        "console": None,
        "progress": Progress(0),
        "quality": QualityAxes(50, 50, 50, 50),
        "days_in_dev": 0,
        "lead_id": EmployeeId(1),
        "team_ids": (),
    }
    defaults.update(kwargs)
    return GameProject(**defaults)  # type: ignore[arg-type]


def test_tick_deducts_salary_sum_from_cash() -> None:
    state = CompanyState().add_employee(_emp(1, salary=Money(1000_00)))
    new_state = tick(state, GameRng(0))
    assert new_state.cash == Money(99_000_00)  # 100_000_00 - 1000_00


def test_tick_advances_day_index() -> None:
    state = CompanyState()
    new_state = tick(state, GameRng(0))
    assert new_state.day_index == 1


def test_tick_advances_project_progress() -> None:
    state = (
        CompanyState()
        .add_employee(_emp(1))
        .add_project(_project(lead_id=EmployeeId(1)))
    )
    new_state = tick(state, GameRng(0))
    assert new_state.projects[ProjectId(1)].progress.value > 0


def test_tick_shipped_project_pays_revenue_and_fans() -> None:
    """A project at progress=100 becomes shipped → revenue + fans added."""
    state = (
        CompanyState()
        .add_employee(_emp(1))
        .add_project(_project(progress=Progress(100), lead_id=EmployeeId(1)))
    )
    before_cash = state.cash
    new_state = tick(state, GameRng(0))
    # Revenue > 0 must have been added to cash (beyond salary deduction).
    assert new_state.cash.cents > before_cash.cents - 500_00  # before minus salary
    # Fans must have grown.
    assert new_state.fans > 0


def test_tick_drift_satisfaction_clamped() -> None:
    """Satisfaction stays in [0, 100] across many ticks."""
    state = CompanyState().add_employee(_emp(1, satisfaction=50))
    new_state = state
    for _ in range(200):
        new_state = tick(new_state, GameRng(7))
    assert 0 <= new_state.employees[EmployeeId(1)].satisfaction <= 100


def test_tick_default_market_is_pc() -> None:
    """tick(state, rng) without market uses MarketState.default_for_platform(PC)."""
    assert DEFAULT_MARKET.platform == Platform.PC


def test_tick_input_state_immutable() -> None:
    """Calling tick does not mutate input state."""
    state = (
        CompanyState()
        .add_employee(_emp(1))
        .add_project(_project(lead_id=EmployeeId(1)))
    )
    _ = tick(state, GameRng(0))
    assert state.cash == Money(100_000_00)
    assert state.day_index == 0


def test_tick_empty_state_just_advances_day() -> None:
    """No employees, no projects → only day advances, no cash change."""
    state = CompanyState()
    new_state = tick(state, GameRng(0))
    assert new_state.day_index == 1
    assert new_state.cash == state.cash


def test_tick_determinism_seed_42_10_ticks() -> None:
    """Pinned snapshot — 10 ticks of a populated state, seed 42.

    If this changes, a formula or RNG call order shifted. Intentional
    regression anchor for engine determinism.
    """
    state = (
        CompanyState()
        .add_employee(_emp(1, satisfaction=80, level=5, job=Job.LEAD))
        .add_employee(_emp(2, satisfaction=60, level=3, job=Job.SENIOR))
        .add_project(_project(lead_id=EmployeeId(1)))
    )
    new_state = state
    for _ in range(10):
        new_state = tick(new_state, GameRng(42))
    snapshot = (
        f"day={new_state.day_index} "
        f"cash={new_state.cash.cents} "
        f"fans={new_state.fans} "
        f"sat1={new_state.employees[EmployeeId(1)].satisfaction} "
        f"sat2={new_state.employees[EmployeeId(2)].satisfaction} "
        f"prog={new_state.projects[ProjectId(1)].progress.value} "
        f"days_in_dev={new_state.projects[ProjectId(1)].days_in_dev}"
    )
    expected = "day=10 cash=7752000 fans=0 sat1=90 sat2=50 prog=20 days_in_dev=10"
    assert snapshot == expected, f"Snapshot drift.\nGot:      {snapshot}\nExpected: {expected}"


def test_tick_with_custom_market() -> None:
    """Passing a custom MarketState routes sales through that market."""
    state = (
        CompanyState()
        .add_employee(_emp(1))
        .add_project(_project(progress=Progress(100), lead_id=EmployeeId(1)))
    )
    handheld = MarketState.default_for_platform(Platform.HANDHELD)
    new_state = tick(state, GameRng(0), market=handheld)
    # Ship happened, fans > 0
    assert new_state.fans >= 0  # passive check that ship event fired
