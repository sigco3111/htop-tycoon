"""Regression tests for tick safety when a ModalScreen is on top.

Background: _tick_one_day calls ``self.query_one(HtopHeader)`` /
``self.query_one(MetricBar)`` to push the latest state into the reactive
widgets. Those widgets belong to the MAIN screen — when a ModalScreen
(StrategyPickerScreen, GameStarterScreen, AwardScreen, EndingScreen)
is pushed on top, ``query_one`` raises ``NoMatches`` and the tick
crashes the app. The simulation MUST keep advancing even when the
modal is showing.
"""
from __future__ import annotations

import pytest

from htop_tycoon.domain import GameState
from htop_tycoon.ui import HtopTycoonApp
from htop_tycoon.ui.screens.strategy_picker import StrategyPickerScreen


@pytest.mark.asyncio
async def test_tick_does_not_crash_when_strategy_picker_open() -> None:
    """_tick_one_day must survive query_one missing during a modal."""
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=1)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("1")
        await pilot.pause()
        day_before = app._state.day
        await pilot.press("s")
        await pilot.pause()
        assert isinstance(app.screen, StrategyPickerScreen)
        for _ in range(5):
            app._tick_one_day()
            await pilot.pause()
        assert app._state.day == day_before + 5, (
            f"tick should advance day even with modal open: "
            f"before={day_before}, after={app._state.day}"
        )


@pytest.mark.asyncio
async def test_tick_does_not_crash_when_game_starter_open() -> None:
    """Same for GameStarterScreen (n)."""
    from htop_tycoon.ui.screens.game_starter import GameStarterScreen

    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=1)
    async with app.run_test() as pilot:
        await pilot.pause()
        day_before = app._state.day
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, GameStarterScreen)
        for _ in range(5):
            app._tick_one_day()
            await pilot.pause()
        assert app._state.day == day_before + 5


@pytest.mark.asyncio
async def test_footer_renders_action_keys_on_first_line() -> None:
    """Single-letter action keys (d/H/n/s) must be visible without scrolling.

    Previously they were rendered AFTER the F-key legend, which pushed
    them off-screen on narrow terminals (default 80-col iTerm2/Terminal.app).
    Now they are on the FIRST line so the user sees them immediately.
    """
    from htop_tycoon.ui.widgets import HtopFooter

    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = str(app.query_one(HtopFooter).render())
        first_line = footer.split("\n", 1)[0]
        for hint in ("[d]", "[H]", "[n]", "[s]"):
            assert hint in first_line, (
                f"action key {hint!r} missing from footer first line: {first_line!r}"
            )
        for hint in ("[F1]", "[F2]"):
            assert hint in footer, f"F-key {hint!r} missing from footer anywhere"
