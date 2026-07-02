"""Tests for action_toggle_tree — F5 toggles OrgTree root expand state."""

from __future__ import annotations

import asyncio

from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.widgets.org_tree import OrgTree


def test_f5_collapse_orgtree_root() -> None:
    """F5 호출 시 OrgTree root가 collapse되어야 함."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            orgtree = app.query_one(OrgTree)
            assert orgtree.root.is_expanded is True, "root는 default expand"

            app.action_toggle_tree()
            await pilot.pause()

            assert orgtree.root.is_expanded is False, (
                "F5 호출 후 root가 collapse되어야 함"
            )

    asyncio.run(_go())


def test_f5_double_call_expand_again() -> None:
    """F5 두 번 호출 시 다시 expand."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            orgtree = app.query_one(OrgTree)
            assert orgtree.root.is_expanded is True

            app.action_toggle_tree()
            await pilot.pause()
            assert orgtree.root.is_expanded is False

            app.action_toggle_tree()
            await pilot.pause()
            assert orgtree.root.is_expanded is True

    asyncio.run(_go())


def test_f5_collapse_persists_after_refresh() -> None:
    """F5로 collapse 후 _refresh_widgets가 호출되어도 root는 collapsed 유지."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            orgtree = app.query_one(OrgTree)

            app.action_toggle_tree()
            await pilot.pause()
            assert orgtree.root.is_expanded is False

            app._refresh_widgets()
            await pilot.pause()

            orgtree_after = app.query_one(OrgTree)
            assert orgtree_after.root.is_expanded is False, (
                "refresh 후 root는 collapsed 유지해야 함"
            )

    asyncio.run(_go())