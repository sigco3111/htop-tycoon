"""Tests for Modal Lock — modal open 중 body refresh skip."""

from __future__ import annotations

from unittest.mock import patch

from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state


def _app() -> HtopTycoonApp:
    return HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))


def test_is_modal_open_returns_false_when_no_modal() -> None:
    app = _app()
    assert app._is_modal_open() is False


def test_is_modal_open_returns_true_when_strategy_picker_pending() -> None:
    from htop_tycoon.domain.enums import StrategyKind
    from htop_tycoon.ui.screens.strategy_picker import StrategyPicker
    app = _app()
    app._pending_strategy_picker = StrategyPicker(StrategyKind.BALANCED)
    assert app._is_modal_open() is True


def test_is_modal_open_returns_true_when_hire_screen_pending() -> None:
    from htop_tycoon.ui.screens.hire import HireScreen
    app = _app()
    app._pending_hire_screen = HireScreen([])
    assert app._is_modal_open() is True


def test_refresh_widgets_skips_body_when_modal_open() -> None:
    """modal이 떠있는 동안 _refresh_widgets가 body를 파괴하지 않음."""
    import asyncio
    app = _app()

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_open_strategy_picker()
            await pilot.pause()
            assert app._is_modal_open() is True

            body = app.query_one("#body")
            initial_children = list(body.children)

            with patch.object(app, "_refresh_footer") as footer_spy:
                app._refresh_widgets()
                footer_spy.assert_called_once()

            after_children = list(body.children)
            assert len(initial_children) == len(after_children), (
                "modal이 떠있을 때 body children이 변경되면 안 됨"
            )

    asyncio.run(_run())


def test_refresh_widgets_full_update_when_no_modal() -> None:
    """modal이 없을 때는 정상적으로 body 갱신."""
    import asyncio
    app = _app()

    async def _run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app._is_modal_open() is False
            app._refresh_widgets()
            await pilot.pause()
            body = app.query_one("#body")
            assert len(body.children) >= 3

    asyncio.run(_run())