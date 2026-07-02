"""Pilot scenario: capture screenshots at t=600, t=1200, t=1800.

Spec §7.7 row 1: 'manual_qa_short.txt' — short playthrough with 3 PNGs (we use SVG).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from htop_tycoon.domain import GameState
from htop_tycoon.ui import HtopTycoonApp

EVIDENCE_DIR = Path(".omo/evidence")


@pytest.mark.asyncio
async def test_screenshot_at_t_600() -> None:
    """Save SVG screenshot at day 600."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        for _ in range(600):
            app._tick_one_day()
        await pilot.pause()
        target = EVIDENCE_DIR / "pilot_short_t600.svg"
        target.unlink(missing_ok=True)
        app.save_screenshot(str(target))
        assert target.exists(), f"screenshot not created at {target}"
        assert target.stat().st_size > 100, f"screenshot too small: {target.stat().st_size} bytes"


@pytest.mark.asyncio
async def test_screenshot_at_t_1200() -> None:
    """Save SVG screenshot at day 1200."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        for _ in range(1200):
            app._tick_one_day()
        await pilot.pause()
        target = EVIDENCE_DIR / "pilot_short_t1200.svg"
        target.unlink(missing_ok=True)
        app.save_screenshot(str(target))
        assert target.exists()
        assert target.stat().st_size > 100


@pytest.mark.asyncio
async def test_screenshot_at_t_1800() -> None:
    """Save SVG screenshot at day 1800."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        for _ in range(1800):
            app._tick_one_day()
        await pilot.pause()
        target = EVIDENCE_DIR / "pilot_short_t1800.svg"
        target.unlink(missing_ok=True)
        app.save_screenshot(str(target))
        assert target.exists()
        assert target.stat().st_size > 100
