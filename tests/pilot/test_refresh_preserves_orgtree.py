"""Tests for app._refresh_widgets — OrgTree cursor 보존."""

from __future__ import annotations

import asyncio

from htop_tycoon.domain import CompanyState
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.widgets.org_tree import OrgTree


def test_refresh_widgets_preserves_orgtree_cursor() -> None:
    """_refresh_widgets 호출 후에도 OrgTree cursor 유지."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            orgtree = app.query_one(OrgTree)
            ada_node = next(
                (n for n in orgtree._tree_nodes.values()
                 if n.data is not None and str(n.data) == "1"),
                None,
            )
            assert ada_node is not None
            orgtree._cursor_node = ada_node

            new_state = mock_state(speed=0)
            object.__setattr__(app, "_state", new_state)
            app._refresh_widgets()
            await pilot.pause()

            orgtree_after = app.query_one(OrgTree)
            cursor_node = orgtree_after._cursor_node
            assert cursor_node is not None, "cursor lost after refresh"
            assert str(cursor_node.data) == "1", (
                f"cursor moved to wrong node: {cursor_node.data!r}"
            )
            assert orgtree_after is orgtree, "OrgTree instance should be preserved"

    asyncio.run(_go())


def test_refresh_widgets_no_modal_skips_no_op_when_no_change() -> None:
    """modal 없을 때 _refresh_widgets는 OrgTree 갱신 (state 변경 시)."""
    async def _go() -> None:
        app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            orgtree = app.query_one(OrgTree)
            original_instance = orgtree
            app._refresh_widgets()
            await pilot.pause()
            orgtree_after = app.query_one(OrgTree)
            assert orgtree_after is original_instance, (
                "OrgTree should not be recreated"
            )

    asyncio.run(_go())