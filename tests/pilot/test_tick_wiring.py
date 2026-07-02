"""S4+ contract: tick() wiring advances CompanyState and refreshes UI.

Pilot test for Phase 2E. Calls _advance_one_tick() 10 times directly
(no real timer — avoids timing flake in tests), then captures SVG to
verify UI reflects the mutated state.
"""

from __future__ import annotations

from pathlib import Path

from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state

SCREENSHOT_DIR: str = "docs/screenshots"
SCREENSHOT_NAME: str = "phase2e_tick_wiring.svg"
TEST_SCREEN_SIZE: tuple[int, int] = (120, 40)
NUM_TICKS: int = 10
RNG_SEED: int = 42


def _normalize_svg(svg: str) -> str:
    return svg.replace("&#160;", " ")


async def test_tick_wiring_advances_state() -> None:
    """10 ticks advance day_index and mutate state; UI reflects new state."""
    app = HtopTycoonApp(
        state=mock_state(speed=0),
        rng=GameRng(seed=RNG_SEED),
    )

    async with app.run_test(size=TEST_SCREEN_SIZE) as pilot:
        await pilot.pause()
        assert app._state.day_index == 0
        assert app._state.cash.cents == 100_000_00

        for _ in range(NUM_TICKS):
            app._advance_one_tick()

        await pilot.pause()

        assert app._state.day_index == NUM_TICKS, (
            f"Expected day_index={NUM_TICKS}, got {app._state.day_index}"
        )

        svg_path = app.save_screenshot(
            filename=SCREENSHOT_NAME,
            path=SCREENSHOT_DIR,
        )

    svg_file = Path(svg_path)
    assert svg_file.exists()

    raw = svg_file.read_text(encoding="utf-8")
    content = _normalize_svg(raw)

    day_marker = f"{app._state.year}년차"
    assert day_marker in content, (
        f"SVG should show '{day_marker}' after {NUM_TICKS} ticks"
    )


async def test_action_set_speed_changes_speed() -> None:
    """action_set_speed updates state.speed and restarts timer."""
    app = HtopTycoonApp(
        state=mock_state(speed=0),
        rng=GameRng(seed=RNG_SEED),
    )

    async with app.run_test(size=TEST_SCREEN_SIZE) as pilot:
        await pilot.pause()
        assert app._state.speed == 0
        app.action_set_speed(3)
        await pilot.pause()
        assert app._state.speed == 3


async def test_action_toggle_pause_toggles_speed() -> None:
    """action_toggle_pause flips between paused (0) and playing (1)."""
    app = HtopTycoonApp(
        state=mock_state(speed=1),
        rng=GameRng(seed=RNG_SEED),
    )

    async with app.run_test(size=TEST_SCREEN_SIZE) as pilot:
        await pilot.pause()
        assert app._state.speed == 1
        app.action_toggle_pause()
        await pilot.pause()
        assert app._state.speed == 0
        app.action_toggle_pause()
        await pilot.pause()
        assert app._state.speed == 1
