"""S5+ contract: F2 saves state to YAML, F9 loads it back unchanged.

Pilot test for Phase 2F. Boots App with isolated save_path (tmp_path),
advances N ticks, saves, advances more ticks, loads, verifies state
restored to the post-save snapshot.
"""

from __future__ import annotations

from pathlib import Path

from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state

SCREENSHOT_DIR: str = "docs/screenshots"
SCREENSHOT_NAME: str = "phase2f_save_load.svg"
TEST_SCREEN_SIZE: tuple[int, int] = (120, 40)
NUM_PRE_SAVE_TICKS: int = 5
NUM_POST_SAVE_TICKS: int = 5
RNG_SEED: int = 42


def _normalize_svg(svg: str) -> str:
    return svg.replace("&#160;", " ")


async def test_save_then_load_restores_snapshot(tmp_path: Path) -> None:
    save_path = tmp_path / "save.yaml"
    app = HtopTycoonApp(
        state=mock_state(speed=0),
        rng=GameRng(seed=RNG_SEED),
        save_path=save_path,
    )

    async with app.run_test(size=TEST_SCREEN_SIZE) as pilot:
        await pilot.pause()

        for _ in range(NUM_PRE_SAVE_TICKS):
            app._advance_one_tick()
        assert app._state.day_index == NUM_PRE_SAVE_TICKS

        app.action_save_game()
        assert save_path.exists()

        snapshot_day = app._state.day_index
        snapshot_cash = app._state.cash.cents

        for _ in range(NUM_POST_SAVE_TICKS):
            app._advance_one_tick()
        assert app._state.day_index == NUM_PRE_SAVE_TICKS + NUM_POST_SAVE_TICKS

        app.action_load_game()
        assert app._state.day_index == snapshot_day, (
            f"Expected day={snapshot_day} after load, got {app._state.day_index}"
        )
        assert app._state.cash.cents == snapshot_cash

        svg_path = app.save_screenshot(
            filename=SCREENSHOT_NAME,
            path=SCREENSHOT_DIR,
        )

    svg_file = Path(svg_path)
    assert svg_file.exists()
    content = _normalize_svg(svg_file.read_text(encoding="utf-8"))
    assert f"Year {app._state.year}" in content


async def test_load_without_save_notifies(tmp_path: Path) -> None:
    save_path = tmp_path / "missing.yaml"
    app = HtopTycoonApp(
        state=mock_state(speed=0),
        rng=GameRng(seed=RNG_SEED),
        save_path=save_path,
    )

    async with app.run_test(size=TEST_SCREEN_SIZE) as pilot:
        await pilot.pause()
        before_day = app._state.day_index
        app.action_load_game()
        await pilot.pause()
        assert app._state.day_index == before_day, "Load should be no-op when file missing"
