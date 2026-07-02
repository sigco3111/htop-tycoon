"""Phase 2H: StrategyPicker widget + 's' key binding."""

from __future__ import annotations

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.strategy_picker import StrategyPicker, render_strategy_picker_text

SCREENSHOT_DIR: str = "docs/screenshots"
SCREENSHOT_NAME: str = "phase2h_strategy_picker.svg"
TEST_SCREEN_SIZE: tuple[int, int] = (120, 40)


def test_picker_renders_currently_selected() -> None:
    text = render_strategy_picker_text(StrategyKind.BALANCED)
    assert "균형" in text
    assert "→ 균형 ←" in text


def test_picker_renders_all_four_options() -> None:
    text = render_strategy_picker_text(StrategyKind.AGGRESSIVE)
    assert "공격적" in text
    assert "보수적" in text
    assert "균형" in text
    assert "장르 집중" in text


def test_picker_select_returns_picked_kind() -> None:
    picker = StrategyPicker(StrategyKind.BALANCED)
    assert picker.select(StrategyKind.AGGRESSIVE) == StrategyKind.AGGRESSIVE
    assert picker.select(StrategyKind.CONSERVATIVE) == StrategyKind.CONSERVATIVE


def test_picker_render_with_genre_focus() -> None:
    text = render_strategy_picker_text(StrategyKind.GENRE_FOCUS)
    assert "장르 집중" in text
    assert "→ 장르 집중 ←" in text


def test_picker_render_output_includes_all_strategies() -> None:
    """Picker's render output covers all 4 strategy names — captured for visual review."""
    text = render_strategy_picker_text(StrategyKind.AGGRESSIVE)
    assert "공격적" in text
    assert "보수적" in text
    assert "균형" in text
    assert "장르 집중" in text
    assert "→ 공격적 ←" in text


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
