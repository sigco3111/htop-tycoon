"""Phase 2J pilot: Release + ConsoleMarket screens."""

from __future__ import annotations

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
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.console import ConsoleMarketScreen, render_console_market_text
from htop_tycoon.ui.screens.release import ReleaseScreen, render_release_text


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


def test_release_screen_empty_state() -> None:
    state = CompanyState()
    screen = ReleaseScreen(state)
    assert "출시 가능한 프로젝트가 없습니다" in render_release_text(list(screen.projects))


def test_release_screen_renders_shipped() -> None:
    state = CompanyState().add_project(_shipped_project())
    screen = ReleaseScreen(state)
    text = render_release_text(list(screen.projects))
    assert "Eldritch Quest" in text
    assert "RPG" in text


def test_release_screen_select_returns_id() -> None:
    state = CompanyState().add_project(_shipped_project())
    screen = ReleaseScreen(state)
    assert screen.select(1) == ProjectId(1)
    assert screen.select(99) is None


def test_console_market_screen_lists_available() -> None:
    state = CompanyState(cash=Money(500_000_00))
    screen = ConsoleMarketScreen(state)
    text = render_console_market_text(state, list(screen.listings))
    assert "NOVA" in text
    assert "PIXEL_2" in text


def test_console_market_excludes_owned() -> None:
    state = CompanyState(cash=Money(500_000_00)).mark_own_console(Console.NOVA)
    screen = ConsoleMarketScreen(state)
    assert Console.NOVA not in screen.listings


def test_console_market_select_returns_console() -> None:
    state = CompanyState(cash=Money(500_000_00))
    screen = ConsoleMarketScreen(state)
    picked = screen.select(1)
    assert isinstance(picked, Console)


def test_app_open_console_market() -> None:
    """action_open_console_market sets _pending_console_screen."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _open() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_open_console_market()
            await pilot.pause()
            assert app._pending_console_screen is not None

    asyncio.run(_open())


def test_app_buy_console() -> None:
    """action_buy_console purchases and updates state."""
    from htop_tycoon.domain import Money as M

    state = CompanyState(cash=M(500_000_00))
    app = HtopTycoonApp(state=state, rng=GameRng(0))

    import asyncio

    async def _buy() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_open_console_market()
            await pilot.pause()
            screen = app._pending_console_screen
            assert screen is not None
            before_cash = app._state.cash.cents
            before_own = screen.select(1)
            assert before_own is not None
            console_value = before_own.value
            app.action_buy_console("1")
            await pilot.pause()
            assert app._state.own_console is not None
            assert app._state.own_console.value == console_value
            assert app._state.cash.cents < before_cash

    asyncio.run(_buy())


def test_app_open_release_screen() -> None:
    """action_open_release_screen sets _pending_release_screen."""
    state = CompanyState().add_project(_shipped_project())
    app = HtopTycoonApp(state=state, rng=GameRng(0))

    import asyncio

    async def _open() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_open_release_screen()
            await pilot.pause()
            assert app._pending_release_screen is not None

    asyncio.run(_open())


def test_app_select_release_target() -> None:
    """action_select_release_target releases and updates state."""
    from htop_tycoon.domain import Money as M

    state = CompanyState(cash=M(500_000_00)).add_project(_shipped_project())
    app = HtopTycoonApp(state=state, rng=GameRng(0))

    import asyncio

    async def _release() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_open_release_screen()
            await pilot.pause()
            assert app._pending_release_screen is not None
            before_cash = app._state.cash.cents
            app.action_select_release_target("1")
            await pilot.pause()
            assert app._pending_release_screen is None
            assert app._state.cash.cents != before_cash

    asyncio.run(_release())
