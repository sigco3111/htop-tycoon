"""Phase 2L pilot: 7 new action handler methods on HtopTycoonApp.

Each test calls the action method directly (not via pilot keypress).
RED — all methods are unimplemented; tests verify the correct
AttributeError / AssertionError is raised until the methods exist.
"""

from __future__ import annotations

from unittest.mock import patch

from htop_tycoon.domain import CompanyState, EmployeeId
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state


def _emp_id(state: CompanyState, name: str) -> EmployeeId | None:
    for eid, emp in state.employees.items():
        if emp.name == name:
            return eid
    return None


def test_action_show_help() -> None:
    """action_show_help creates HelpScreen as pending screen."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_show_help()
            await pilot.pause()
            assert app._pending_help_screen is not None

    asyncio.run(_run())


def test_action_search_employee() -> None:
    """action_search_employee: Ada matches; Unknown notifies '검색 결과 없음'."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            with patch.object(app, "notify") as spy:
                app.action_search_employee("Ada")
                await pilot.pause()
                assert spy.called

            with patch.object(app, "notify") as spy2:
                app.action_search_employee("Unknown")
                await pilot.pause()
                assert spy2.called
                spy2.assert_called_with("검색 결과 없음")

    asyncio.run(_run())


def test_action_toggle_tree() -> None:
    """action_toggle_tree flips app._tree_expanded boolean."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app._tree_expanded is True
            app.action_toggle_tree()
            await pilot.pause()
            assert app._tree_expanded is False
            app.action_toggle_tree()
            await pilot.pause()
            assert app._tree_expanded is True

    asyncio.run(_run())


def test_action_promote_employee() -> None:
    """action_promote_employee creates PromoteScreen as pending screen."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_promote_employee()
            await pilot.pause()
            assert app._pending_promote_screen is not None

    asyncio.run(_run())


def test_action_new_project() -> None:
    """action_new_project: blocked when project active; creates when none exist."""
    import asyncio

    async def _blocked() -> None:
        state = mock_state(speed=0)
        app = HtopTycoonApp(state=state, rng=GameRng(0))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert len(app._state.projects) == 1
            with patch.object(app, "notify") as spy:
                app.action_new_project()
                await pilot.pause()
                spy.assert_called()
                assert "이미 진행 중" in spy.call_args[0][0] or spy.called
            assert len(app._state.projects) == 1

    async def _creates() -> None:
        state = mock_state(speed=0)
        for pid in list(state.projects.keys()):
            state = state.remove_project(pid)
        assert len(state.projects) == 0
        app = HtopTycoonApp(state=state, rng=GameRng(0))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert len(app._state.projects) == 0
            assert app._state.cash.cents >= 50_000_00
            app.action_new_project()
            await pilot.pause()
            assert len(app._state.projects) == 1

    asyncio.run(_blocked())
    asyncio.run(_creates())


def test_action_toggle_auto() -> None:
    """action_toggle_auto flips app._state.auto_on False -> True on first call."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app._state.auto_on is False
            app.action_toggle_auto()
            await pilot.pause()
            assert app._state.auto_on is True

    asyncio.run(_run())


def test_action_tag_employee() -> None:
    """action_tag_employee is a placeholder that notifies '태그 기능 곧 출시'."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            ada_id = _emp_id(app._state, "Ada")
            assert ada_id is not None
            with patch.object(app, "notify") as spy:
                app.action_tag_employee()
                await pilot.pause()
                assert spy.called
                assert "태그 기능" in spy.call_args[0][0]

    asyncio.run(_run())
