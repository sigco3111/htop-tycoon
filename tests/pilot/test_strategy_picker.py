"""htop-tycoon v3.0 — Pilot scenario 2: strategy_picker (spec §7.4).

Verifies that pressing 's' opens the StrategyPickerScreen, the screen
shows the 4 spec §3.1 strategies (balanced / aggressive / conservative /
genre_focus), and pressing escape dismisses without selecting.
"""
from __future__ import annotations

import pytest

from htop_tycoon.domain import GameState
from htop_tycoon.ui import HtopTycoonApp
from htop_tycoon.ui.screens.strategy_picker import (
    STRATEGY_NAMES,
    StrategyPickerScreen,
)


@pytest.mark.asyncio
async def test_strategy_picker_opens_on_s_key() -> None:
    """Pilot scenario 2: press 's' -> StrategyPickerScreen shows 4 options."""
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Press 's' — should push the strategy picker screen
        await pilot.press("s")
        await pilot.pause()
        # The current screen should now be StrategyPickerScreen
        assert isinstance(app.screen, StrategyPickerScreen)
        # The 4 spec strategies should be available
        assert set(STRATEGY_NAMES) == {"balanced", "aggressive", "conservative", "genre_focus"}


@pytest.mark.asyncio
async def test_strategy_picker_dismiss_on_escape() -> None:
    """Escape dismisses the picker without selecting (returns None)."""
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        assert isinstance(app.screen, StrategyPickerScreen)
        # Press escape — should pop back to main
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, StrategyPickerScreen)


@pytest.mark.asyncio
async def test_strategy_picker_selects_strategy_on_button() -> None:
    """Clicking a strategy button dismisses with the strategy name."""
    from htop_tycoon.ui.screens.strategy_picker import StrategyPickerScreen as SPS

    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    strategy_chosen: list[str | None] = [None]

    async def on_dismiss(result: str | None) -> None:
        strategy_chosen[0] = result

    async with app.run_test() as pilot:
        await pilot.pause()
        await app.push_screen(SPS(), callback=on_dismiss)
        await pilot.pause()
        # Click the "balanced" button
        await pilot.click("#btn-balanced")
        await pilot.pause()
        assert strategy_chosen[0] == "balanced"
        # app.active_strategy should now reflect the selection
        assert app.active_strategy == "balanced"
