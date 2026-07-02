"""Tests for modal close via _close_modal — modal lifecycle 완료 확인."""

from __future__ import annotations

import asyncio

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.strategy_picker import StrategyPicker


def test_close_modal_dismisses_screen_completely() -> None:
    """_close_modal 호출 시 modal이 screen_stack에서 사라지고 _pending도 정리."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            modal = StrategyPicker(StrategyKind.BALANCED)
            app._open_pending("_pending_strategy_picker", modal)
            await pilot.pause()
            assert len(app.screen_stack) == 2
            assert app._pending_strategy_picker is not None

            app._close_modal()
            await pilot.pause()
            assert len(app.screen_stack) == 1, (
                f"modal이 닫혔는데 screen_stack이 {len(app.screen_stack)} (expected 1)"
            )
            assert app._pending_strategy_picker is None

    asyncio.run(_go())


def test_close_modal_idempotent_safe_to_call_twice() -> None:
    """_close_modal이 두 번 호출되어도 안전."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            modal = StrategyPicker(StrategyKind.BALANCED)
            app._open_pending("_pending_strategy_picker", modal)
            await pilot.pause()

            app._close_modal()
            await pilot.pause()
            app._close_modal()  # 두 번째 — 안전해야 함
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert app._pending_strategy_picker is None

    asyncio.run(_go())


def test_close_modal_no_op_when_no_modal() -> None:
    """modal 없을 때 _close_modal은 no-op."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert len(app.screen_stack) == 1
            app._close_modal()
            await pilot.pause()
            assert len(app.screen_stack) == 1

    asyncio.run(_go())


def test_tick_resumes_after_modal_closed() -> None:
    """modal 닫힌 후 다음 tick이 정상 진행."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            modal = StrategyPicker(StrategyKind.BALANCED)
            app._open_pending("_pending_strategy_picker", modal)
            await pilot.pause()
            assert app._is_modal_open() is True

            app._advance_one_tick()
            assert app._state.day_index == 0  # tick paused

            app._close_modal()
            await pilot.pause()
            assert app._is_modal_open() is False

            app._advance_one_tick()
            assert app._state.day_index == 1  # tick resumed

    asyncio.run(_go())