"""Phase 2J: Console market + release logic."""

from __future__ import annotations

import pytest

from htop_tycoon.domain import (
    CompanyState,
    Console,
    GameProject,
    GameTitle,
    Genre,
    Money,
    Platform,
    Progress,
    ProjectId,
    QualityAxes,
)
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine.console_market import (
    CONSOLE_PRICES,
    available_consoles,
    console_price,
    purchase_console,
)
from htop_tycoon.engine.market import MarketState
from htop_tycoon.engine.release import release_project, releaseable_projects


def _shipped_project(pid: int = 1) -> GameProject:
    return GameProject(
        id=ProjectId(pid),
        title=GameTitle("Eldritch Quest"),
        genre=Genre.RPG,
        platform=Platform.PC,
        console=None,
        progress=Progress(100),
        quality=QualityAxes(80, 70, 60, 50),
        days_in_dev=100,
        lead_id=None,
        team_ids=(),
    )


def test_console_price_zero_for_pc() -> None:
    assert console_price(Console.PC) == Money(0)


def test_console_price_table_complete() -> None:
    for console in Console:
        assert console in CONSOLE_PRICES


def test_available_consoles_excludes_pc() -> None:
    listings = available_consoles()
    assert Console.PC not in listings
    for console in listings:
        assert console_price(console).cents > 0


def test_purchase_console_deducts_cash_and_sets_own() -> None:
    state = CompanyState(cash=Money(200_000_00))
    new_state = purchase_console(state, Console.NOVA)
    assert new_state.own_console == Console.NOVA
    assert new_state.cash.cents == 200_000_00 - console_price(Console.NOVA).cents


def test_purchase_console_already_owned_raises() -> None:
    state = CompanyState(cash=Money(200_000_00)).mark_own_console(Console.NOVA)
    with pytest.raises(ValueError):
        purchase_console(state, Console.NOVA)


def test_purchase_console_insufficient_cash_raises() -> None:
    state = CompanyState(cash=Money(10_000_00))
    with pytest.raises(ValueError):
        purchase_console(state, Console.NOVA)


def test_releaseable_projects_filters_shipped() -> None:
    state = CompanyState().add_project(_shipped_project())
    state = state.add_project(
        GameProject(
            id=ProjectId(2),
            title=GameTitle("In Progress"),
            genre=Genre.ACTION,
            platform=Platform.PC,
            console=None,
            progress=Progress(50),
            quality=QualityAxes(50, 50, 50, 50),
            days_in_dev=50,
            lead_id=None,
            team_ids=(),
        )
    )
    released = releaseable_projects(state)
    assert len(released) == 1
    assert str(released[0].title) == "Eldritch Quest"


def test_release_project_adds_revenue() -> None:
    state = CompanyState(cash=Money(0)).add_project(_shipped_project())
    market = MarketState.default_for_platform(Platform.PC)
    new_state = release_project(
        state, ProjectId(1), Console.NOVA, market, GameRng(0)
    )
    assert new_state.cash.cents > 0


def test_release_project_assigns_console() -> None:
    state = CompanyState().add_project(_shipped_project())
    market = MarketState.default_for_platform(Platform.PC)
    new_state = release_project(
        state, ProjectId(1), Console.NOVA, market, GameRng(0)
    )
    assert new_state.projects[ProjectId(1)].console == Console.NOVA


def test_release_project_assigns_console_and_units() -> None:
    from htop_tycoon.domain import EmployeeId

    proj = GameProject(
        id=ProjectId(1),
        title=GameTitle("Blockbuster"),
        genre=Genre.RPG,
        platform=Platform.PC,
        console=None,
        progress=Progress(100),
        quality=QualityAxes(100, 100, 100, 100),
        days_in_dev=200,
        lead_id=EmployeeId(1),
        team_ids=(),
    )
    state = CompanyState().add_project(proj)
    market = MarketState.default_for_platform(Platform.PC)
    new_state = release_project(
        state, ProjectId(1), Console.NOVA, market, GameRng(0)
    )
    assert new_state.projects[ProjectId(1)].console == Console.NOVA
    assert new_state.projects[ProjectId(1)].units_sold > 0


def test_release_project_missing_id_raises() -> None:
    state = CompanyState()
    market = MarketState.default_for_platform(Platform.PC)
    with pytest.raises(ValueError):
        release_project(state, ProjectId(99), Console.NOVA, market, GameRng(0))


def test_release_project_unshipped_raises() -> None:
    from htop_tycoon.domain import EmployeeId

    proj = GameProject(
        id=ProjectId(1),
        title=GameTitle("Not Ready"),
        genre=Genre.RPG,
        platform=Platform.PC,
        console=None,
        progress=Progress(50),
        quality=QualityAxes(50, 50, 50, 50),
        days_in_dev=50,
        lead_id=EmployeeId(1),
        team_ids=(),
    )
    state = CompanyState().add_project(proj)
    market = MarketState.default_for_platform(Platform.PC)
    with pytest.raises(ValueError):
        release_project(state, ProjectId(1), Console.NOVA, market, GameRng(0))
