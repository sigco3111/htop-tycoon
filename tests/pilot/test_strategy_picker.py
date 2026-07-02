"""Phase 2H: StrategyPicker widget + 's' key binding."""

from __future__ import annotations

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.strategy_picker import StrategyPicker

SCREENSHOT_DIR: str = "docs/screenshots"
SCREENSHOT_NAME: str = "phase2h_strategy_picker.svg"
TEST_SCREEN_SIZE: tuple[int, int] = (120, 40)


def test_picker_renders_currently_selected() -> None:
    picker = StrategyPicker(StrategyKind.BALANCED)
    text = picker.render()
    assert "Balanced" in text
    assert "→ Balanced ←" in text


def test_picker_renders_all_four_options() -> None:
    picker = StrategyPicker(StrategyKind.AGGRESSIVE)
    text = picker.render()
    assert "Aggressive" in text
    assert "Conservative" in text
    assert "Balanced" in text
    assert "Genre Focus" in text


def test_picker_select_returns_picked_kind() -> None:
    picker = StrategyPicker(StrategyKind.BALANCED)
    assert picker.select(StrategyKind.AGGRESSIVE) == StrategyKind.AGGRESSIVE
    assert picker.select(StrategyKind.CONSERVATIVE) == StrategyKind.CONSERVATIVE


def test_picker_render_with_genre_focus() -> None:
    picker = StrategyPicker(StrategyKind.GENRE_FOCUS)
    text = picker.render()
    assert "Genre Focus" in text
    assert "→ Genre Focus ←" in text


def test_picker_render_output_includes_all_strategies() -> None:
    """Picker's render() output covers all 4 strategy names — captured for visual review."""
    picker = StrategyPicker(StrategyKind.AGGRESSIVE)
    text = picker.render()
    assert "Aggressive" in text
    assert "Conservative" in text
    assert "Balanced" in text
    assert "Genre Focus" in text
    assert "→ Aggressive ←" in text


def test_app_s_key_opens_picker() -> None:
    """action_open_strategy_picker constructs a StrategyPicker instance."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _open() -> None:
        async with app.run_test(size=TEST_SCREEN_SIZE) as pilot:
            await pilot.pause()
            app.action_open_strategy_picker()
            await pilot.pause()
            assert app._pending_strategy_picker is not None
            current: object = app._pending_strategy_picker.current
            assert current == StrategyKind.BALANCED

    asyncio.run(_open())


def test_app_select_strategy_changes_state() -> None:
    """action_select_strategy('AGGRESSIVE') updates state.strategy."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _select() -> None:
        async with app.run_test(size=TEST_SCREEN_SIZE) as pilot:
            await pilot.pause()
            initial = app._state.strategy
            assert initial.value == "BALANCED"
            app.action_select_strategy("AGGRESSIVE")
            await pilot.pause()
            after = app._state.strategy
            assert after.value == "AGGRESSIVE"

    asyncio.run(_select())
