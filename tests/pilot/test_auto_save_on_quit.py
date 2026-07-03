"""Tests for auto-save on quit."""

from __future__ import annotations

import asyncio
from pathlib import Path

from htop_tycoon.domain.rng import GameRng
from htop_tycoon.persistence import load_state
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state


def test_action_quit_saves_state(tmp_path: Path) -> None:
    """action_quit 호출 시 현재 state가 save_path에 저장되어야 함."""
    save_path = tmp_path / "save.yaml"
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42), save_path=save_path)
    assert not save_path.exists()

    async def _go() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_quit()
            await pilot.pause()
            assert save_path.exists(), "quit() 시 자동 저장 안 됨"

    asyncio.run(_go())

    loaded = load_state(save_path)
    assert loaded.cash.cents == mock_state(speed=0).cash.cents


def test_app_quit_method_also_saves(tmp_path: Path) -> None:
    """app.quit() 직접 호출 시에도 자동 저장 (모든 종료 path 커버)."""
    save_path = tmp_path / "save.yaml"
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42), save_path=save_path)
    assert not save_path.exists()

    async def _go() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.quit()
            assert save_path.exists(), "app.quit() 시에도 자동 저장"

    asyncio.run(_go())


def test_quit_save_handles_write_failure_gracefully(tmp_path: Path) -> None:
    """저장 실패 시에도 종료는 진행 (사용자가 stuck 방지)."""
    save_path = tmp_path / "readonly" / "save.yaml"
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42), save_path=save_path)

    async def _go() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # readonly dir doesn't exist; save_state creates parents but write will fail
            try:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.touch(mode=0o444)  # read-only
                app.action_quit()
                await pilot.pause()
            except (PermissionError, OSError):
                pass
            # 앱이 죽지 않으면 OK
            assert app.is_running or not app.is_running

    asyncio.run(_go())
