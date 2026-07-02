"""Tests for Header refresh — modal 활성 시에도 누적 안 됨."""

from __future__ import annotations

import asyncio

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.strategy_picker import StrategyPicker
from htop_tycoon.ui.widgets.header import Header as HtopHeader


def test_refresh_header_uses_app_screen_not_modal() -> None:
    """modal이 활성일 때 _refresh_header가 modal이 아닌 app screen의 Header를 갱신."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            initial_count = len(list(app.screen_stack[0].query(HtopHeader)))
            assert initial_count == 1, (
                f"Expected 1 HtopHeader on app screen, got {initial_count}"
            )

            # modal 열기
            app._pending_strategy_picker = StrategyPicker(StrategyKind.BALANCED)
            app.push_screen(StrategyPicker(StrategyKind.BALANCED))
            await pilot.pause()
            assert len(app.screen_stack) == 2  # main + modal

            # _refresh_header 여러 번 호출
            for _ in range(5):
                app._refresh_header()
                await pilot.pause()

            # Header 인스턴스 수 확인 (누적 안 됨)
            app_screen_count = len(list(app.screen_stack[0].query(HtopHeader)))
            assert app_screen_count == 1, (
                f"Expected 1 HtopHeader on app screen after refresh, got {app_screen_count}"
            )

    asyncio.run(_go())


def test_refresh_header_updates_content_even_with_modal() -> None:
    """modal 활성 상태에서도 Header 내용 갱신이 main screen에 적용됨."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from htop_tycoon.ui.screens.strategy_picker import StrategyPicker
            app.push_screen(StrategyPicker(StrategyKind.BALANCED))
            await pilot.pause()

            for _ in range(3):
                app._refresh_header()
                await pilot.pause()

            app_header = app.screen_stack[0].query(HtopHeader).first()
            assert app_header is not None, "main screen에 HtopHeader 없음"
            assert len(list(app.screen_stack[1].query(HtopHeader))) == 0, (
                "modal screen에 HtopHeader 누적되면 안 됨"
            )

    asyncio.run(_go())