"""Tests for Tick Pause — modal 떠있을 때 게임 시간 정지."""

from __future__ import annotations

import asyncio

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.strategy_picker import StrategyPicker


def test_advance_one_tick_skipped_when_modal_open() -> None:
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=1), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app._pending_strategy_picker = StrategyPicker(StrategyKind.BALANCED)
            initial_day = app._state.day_index
            initial_cash = app._state.cash.cents
            for _ in range(3):
                app._advance_one_tick()
            assert app._state.day_index == initial_day
            assert app._state.cash.cents == initial_cash

    asyncio.run(_go())


def test_advance_one_tick_runs_when_no_modal() -> None:
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=1), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app._is_modal_open() is False
            initial_day = app._state.day_index
            app._advance_one_tick()
            assert app._state.day_index == initial_day + 1

    asyncio.run(_go())


def test_advance_one_tick_runs_again_after_modal_dismissed() -> None:
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=1), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app._pending_strategy_picker = StrategyPicker(StrategyKind.BALANCED)
            for _ in range(5):
                app._advance_one_tick()
            assert app._state.day_index == 0
            app._pending_strategy_picker = None
            initial_day = app._state.day_index
            app._advance_one_tick()
            assert app._state.day_index == initial_day + 1

    asyncio.run(_go())