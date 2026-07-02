"""Regression test for footer height — must NOT be squeezed to 1 row.

Background: the OrgTree widget has ``height: 1fr`` (fills remaining
vertical space). When the screen is tall and the body widgets are
small, OrgTree expands and squeezes the footer (which uses
``dock: bottom; height: 2``) down to a single row. The first line
of the footer then gets clipped, hiding the rest of the action
keys and the entire speed legend.

Fix: HtopFooter CSS has ``min-height: 2`` so Textual's shrink policy
cannot compress it below 2 rows. OrgTree has ``max-height: 12`` so
it cannot grow unboundedly and dominate the screen.

This test asserts the rendered footer region is at least 2 rows tall
on a 30-row screen.
"""
from __future__ import annotations

import pytest

from htop_tycoon.domain import GameState
from htop_tycoon.ui import HtopTycoonApp
from htop_tycoon.ui.widgets import HtopFooter


@pytest.mark.asyncio
async def test_footer_is_two_rows_tall_not_squeezed() -> None:
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = app.query_one(HtopFooter)
        region_height = footer.region.height
        assert region_height >= 2, (
            f"footer region height = {region_height} rows, "
            f"OrgTree is squeezing the footer (should be >= 2)"
        )


@pytest.mark.asyncio
async def test_footer_renders_both_lines_with_all_action_keys() -> None:
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = app.query_one(HtopFooter)
        rendered = footer.render()
        lines = rendered.split("\n")
        assert len(lines) == 2, f"footer should have 2 lines, got {len(lines)}: {rendered!r}"
        assert "[H]고용" in lines[0]
        assert "[n]새게임" in lines[0]
        assert "[g]진행" in lines[0]
        assert "[s]전략" in lines[0]
        assert "[d]Auto" in lines[0]
        assert "[a]시상" in lines[0]
        assert "[c]콘솔" in lines[0]
        assert "[F1]" in lines[1]
        assert "[F10]" in lines[1]
