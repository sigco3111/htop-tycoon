"""Tests that action_open_* methods bypass modals when auto_on=True."""

from __future__ import annotations

from unittest.mock import patch

from htop_tycoon.domain import (
    CompanyState,
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


def _app_with_auto_on() -> HtopTycoonApp:
    state = mock_state(speed=0).toggle_auto()
    return HtopTycoonApp(state=state, rng=GameRng(0))


def test_action_open_strategy_picker_bypassed_when_auto_on() -> None:
    import asyncio
    app = _app_with_auto_on()

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            with patch.object(app, "notify") as spy:
                app.action_open_strategy_picker()
                await pilot.pause()
                spy.assert_called()
                assert "자동" in spy.call_args[0][0]
            assert app._pending_strategy_picker is None

    asyncio.run(_run())


def test_action_open_hire_screen_bypassed_when_auto_on() -> None:
    import asyncio
    app = _app_with_auto_on()

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            with patch.object(app, "notify") as spy:
                app.action_open_hire_screen()
                await pilot.pause()
                spy.assert_called()
                assert "자동" in spy.call_args[0][0]
            assert app._pending_hire_screen is None

    asyncio.run(_run())


def test_action_open_fire_screen_bypassed_when_auto_on() -> None:
    import asyncio
    app = _app_with_auto_on()

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            with patch.object(app, "notify") as spy:
                app.action_open_fire_screen()
                await pilot.pause()
                spy.assert_called()
                assert "자동" in spy.call_args[0][0]
            assert app._pending_fire_screen is None

    asyncio.run(_run())


def test_action_open_release_screen_bypassed_when_auto_on() -> None:
    import asyncio
    state_with_shipped = mock_state(speed=0).toggle_auto().add_project(
        GameProject(
            id=ProjectId(99),
            title=GameTitle("Shipped"),
            genre=Genre.RPG,
            platform=Platform.PC,
            console=None,
            progress=Progress(100),
            quality=QualityAxes(80, 70, 60, 50),
            days_in_dev=100,
            lead_id=None,
            team_ids=(),
        )
    )
    app = HtopTycoonApp(state=state_with_shipped, rng=GameRng(0))

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            with patch.object(app, "notify") as spy:
                app.action_open_release_screen()
                await pilot.pause()
                spy.assert_called()
                assert "자동" in spy.call_args[0][0]
            assert app._pending_release_screen is None

    asyncio.run(_run())


def test_action_open_console_market_bypassed_when_auto_on() -> None:
    import asyncio
    app = _app_with_auto_on()

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            with patch.object(app, "notify") as spy:
                app.action_open_console_market()
                await pilot.pause()
                spy.assert_called()
                assert "자동" in spy.call_args[0][0]
            assert app._pending_console_screen is None

    asyncio.run(_run())


def test_action_request_sell_bypassed_when_auto_on() -> None:
    import asyncio
    state = mock_state(speed=0).toggle_auto()
    state = state.set_voluntary_sale_pending(False)
    app = HtopTycoonApp(state=state, rng=GameRng(0))

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app._state.voluntary_sale_pending is False
            with patch.object(app, "notify") as spy:
                app.action_request_sell()
                await pilot.pause()
                spy.assert_called()
            assert app._state.voluntary_sale_pending is False

    asyncio.run(_run())


def test_action_new_project_bypassed_when_auto_on() -> None:
    import asyncio
    state = mock_state(speed=0).toggle_auto().remove_project(
        next(iter(mock_state(speed=0).projects.keys()))
    )
    app = HtopTycoonApp(state=state, rng=GameRng(0))

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            initial_proj_count = len(app._state.projects)
            with patch.object(app, "notify") as spy:
                app.action_new_project()
                await pilot.pause()
                spy.assert_called()
                assert "자동" in spy.call_args[0][0]
            assert len(app._state.projects) == initial_proj_count

    asyncio.run(_run())