"""Regression tests for live-tick keyboard controls.

Background: the previous action_speed_0..4 handlers only updated the
status text widget but never restarted the per-day timer — so pressing
a speed key from speed=0 (the default) left the game paused forever.
This test pins the fix.
"""
from __future__ import annotations

import pytest

from htop_tycoon.domain import GameState
from htop_tycoon.ui import HtopTycoonApp
from htop_tycoon.ui.widgets import HtopFooter


@pytest.mark.asyncio
async def test_speed_key_1_starts_tick_timer_when_paused() -> None:
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.speed == 0
        assert app._timer is None
        await pilot.press("1")
        await pilot.pause()
        assert app.speed == 1
        assert app._timer is not None


@pytest.mark.asyncio
async def test_speed_key_advances_game_day() -> None:
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        await pilot.pause(1.2)
        assert app._state.day >= 2, f"expected day >= 2 after ~1.2s at 3x, got {app._state.day}"


@pytest.mark.asyncio
async def test_speed_key_0_stops_tick_timer() -> None:
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=1)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("0")
        await pilot.pause()
        assert app.speed == 0
        assert app._timer is None
        day_at_stop = app._state.day
        await pilot.pause(1.0)
        assert app._state.day == day_at_stop, "day should not advance when paused"


@pytest.mark.asyncio
async def test_speed_change_restarts_timer_at_new_rate() -> None:
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=1)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("0")
        await pilot.pause()
        assert app._timer is None
        await pilot.press("3")
        await pilot.pause()
        assert app._timer is not None
        assert app.speed == 3


@pytest.mark.asyncio
async def test_footer_lists_action_keys_so_user_can_discover_them() -> None:
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = str(app.query_one(HtopFooter).render())
        for hint in ("[d] Auto", "[H]", "[n]", "[s]", "[0]", "[1]"):
            assert hint in footer, f"footer missing hint {hint!r}: {footer!r}"


@pytest.mark.asyncio
async def test_toggle_auto_works() -> None:
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.auto_mode is False
        await pilot.press("d")
        await pilot.pause()
        assert app.auto_mode is True
        await pilot.press("d")
        await pilot.pause()
        assert app.auto_mode is False
