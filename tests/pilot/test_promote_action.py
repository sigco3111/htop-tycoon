"""Tests for promote screen — 숫자 키로 직원 승진 처리."""

from __future__ import annotations

import asyncio

from htop_tycoon.domain import CompanyState, EmployeeId
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.promote import PromoteScreen


def test_promote_screen_selects_employee_by_digit() -> None:
    """PromoteScreen 1번 키 누르면 Ada (LEAD L5 sat 85) 승진."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            modal = PromoteScreen(app._state)
            app._open_pending("_pending_promote_screen", modal)
            await pilot.pause()

            ada_id = EmployeeId(1)
            ada_before = app._state.employees[ada_id]
            assert ada_before.level == 5
            assert ada_before.job.value == "LEAD"

            app.action_select_promote_target("1")
            await pilot.pause()

            ada_after = app._state.employees[ada_id]
            assert ada_after.level == 6, (
                f"Ada level should be 6 after promote, got {ada_after.level}"
            )
            assert app._pending_promote_screen is None

    asyncio.run(_go())


def test_promote_screen_invalid_index_no_op() -> None:
    """잘못된 인덱스 선택 시 notify만, 직원 변동 없음."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            modal = PromoteScreen(app._state)
            app._open_pending("_pending_promote_screen", modal)
            await pilot.pause()

            ada_id = EmployeeId(1)
            level_before = app._state.employees[ada_id].level

            app.action_select_promote_target("99")
            await pilot.pause()

            assert app._state.employees[ada_id].level == level_before
            assert app._pending_promote_screen is not None, (
                "잘못된 선택 시 modal 유지"
            )

    asyncio.run(_go())


def test_promote_screen_dismiss_after_select() -> None:
    """승진 선택 후 modal 닫힘 + 화면 stack 줄어듦."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            modal = PromoteScreen(app._state)
            app._open_pending("_pending_promote_screen", modal)
            await pilot.pause()
            assert len(app.screen_stack) == 2

            app.action_select_promote_target("1")
            await pilot.pause()
            assert len(app.screen_stack) == 1, (
                "승진 선택 후 modal 닫혀야 함"
            )

    asyncio.run(_go())