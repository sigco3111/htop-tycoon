"""Debug test: _is_modal_open() lifecycle with real ModalScreen dismiss."""

from __future__ import annotations

import asyncio

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state


def test_is_modal_open_after_dismiss_via_action_select() -> None:
    """action_select_* sets _pending = None, then pop_screen. _is_modal_open should be False."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_open_strategy_picker()
            await pilot.pause()
            assert app._pending_strategy_picker is not None
            assert app._is_modal_open() is True
            app.action_select_strategy("AGGRESSIVE")
            await pilot.pause()
            assert app._pending_strategy_picker is None
            assert app._is_modal_open() is False

    asyncio.run(_go())


def test_advance_one_tick_after_select_strategy_runs() -> None:
    """After action_select_strategy, _advance_one_tick should advance state."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            initial_day = app._state.day_index
            app._advance_one_tick()
            assert app._state.day_index == initial_day + 1, (
                f"Expected {initial_day + 1}, got {app._state.day_index}"
            )

    asyncio.run(_go())


def test_is_modal_open_false_after_escape() -> None:
    """After pressing Escape to dismiss modal, _is_modal_open should be False."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_open_strategy_picker()
            await pilot.pause()
            assert app._is_modal_open() is True
            await pilot.press("escape")
            await pilot.pause()
            assert app._is_modal_open() is False
            assert app._pending_strategy_picker is None

    asyncio.run(_go())