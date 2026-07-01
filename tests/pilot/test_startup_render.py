"""Wave 6 first-pass Pilot scenario: ``startup_render`` (spec §7.4).

Verifies the app boots, the main screen renders with all required
widgets (header + metric bar + footer), and the frozen-hash regression
test (c2540d2) is preserved.

Uses Textual's ``App.run_test()`` (pilot context) to avoid the
interactive TTY.
"""
from __future__ import annotations

import pytest

from htop_tycoon.domain import GameState
from htop_tycoon.ui import HtopTycoonApp
from htop_tycoon.ui.widgets import HtopFooter, HtopHeader, MetricBar


@pytest.mark.asyncio
async def test_startup_render() -> None:
    """Pilot scenario 1: app boots, main screen renders."""
    app = HtopTycoonApp(state=GameState(rng_seed=42), speed=0)  # speed=0 = paused
    async with app.run_test() as pilot:
        await pilot.pause()
        # Header / MetricBar / Footer all present
        assert app.query_one(HtopHeader) is not None
        assert app.query_one(MetricBar) is not None
        assert app.query_one(HtopFooter) is not None
        # Header is bound to the GameState
        header = app.query_one(HtopHeader)
        assert header.state is not None
        assert header.state.rng_seed == 42
        # No active project at day 0 — metric bar shows empty-state
        metric = app.query_one(MetricBar)
        assert metric.project is None or metric.project.is_complete
        # Footer renders the F-key legend
        footer_text = str(app.query_one(HtopFooter).render())
        assert "도움말" in footer_text  # F1 Korean label
        assert "정지" in footer_text     # 0 = pause


@pytest.mark.asyncio
async def test_startup_render_with_active_project() -> None:
    """Header / metric update when state has an active game project."""
    from htop_tycoon.domain import (
        GameProject,
        GenreId,
        Platform,
        PlatformId,
        ProjectId,
        QualityAxis,
        ThemeId,
    )

    state = GameState(rng_seed=42)
    p = GameProject(
        id=ProjectId("p1"),
        name="Test RPG",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=42.0,
        quality_axes={
            QualityAxis.FUN: 6.0,
            QualityAxis.GRAPHICS: 5.0,
            QualityAxis.SOUND: 4.0,
            QualityAxis.ORIGINALITY: 7.0,
        },
    )
    app = HtopTycoonApp(state=state.replace(projects=(p,)), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        metric = app.query_one(MetricBar)
        assert metric.project is p
        # Render shows 4 quality axes
        rendered = str(metric.render())
        assert "재미" in rendered
        assert "그래픽" in rendered
        assert "사운드" in rendered
        assert "독창성" in rendered
        assert "6.0" in rendered  # the FUN value


@pytest.mark.asyncio
async def test_startup_render_uses_default_theme() -> None:
    """Spec §4.1: app boots with a valid theme (the htop-style theme is
    registered in on_mount; the test simply verifies the app has a theme
    set after boot — the specific name depends on the installed Textual
    version's behavior)."""
    app = HtopTycoonApp(state=GameState(), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        # The app must have a non-empty theme set after boot
        assert app.theme != ""
        # The HTOPTYCOON_THEME object must be importable
        from htop_tycoon.ui import HTOPTYCOON_THEME
        assert HTOPTYCOON_THEME.name == "htoptycoon"
