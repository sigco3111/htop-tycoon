"""T7 pilot: EndingScreen + LegacyPanel render."""

from __future__ import annotations

from htop_tycoon.engine.endings import Ending, EndingKind, LegacyScore
from htop_tycoon.ui.screens.ending import (
    ENDING_LABELS,
    EndingScreen,
    LegacyPanel,
)

SCREENSHOT_DIR: str = "docs/screenshots"
SCREENSHOT_NAME: str = "phase2g_ending.svg"
TEST_SCREEN_SIZE: tuple[int, int] = (120, 40)


def test_ending_screen_renders_ending_summary() -> None:
    ending = Ending(
        kind=EndingKind.BANKRUPTCY,
        triggered_at=(3, 42),
        description="Your company went bankrupt.",
    )
    legacy = LegacyScore(
        ending_kind=EndingKind.BANKRUPTCY,
        ending_year=3,
        ending_cash_cents=-55_000_00,
        total_fans=120,
        games_shipped=4,
        mega_hits=1,
    )
    screen = EndingScreen(ending, legacy)
    text = screen.render()
    assert "Bankruptcy" in text
    assert "Year 3" in text
    assert "-$55,000" in text
    assert "Fans: 120" in text
    assert "Games Shipped: 4" in text
    assert "Mega Hits: 1" in text
    assert "[New Game]" in text
    assert "[Quit]" in text


def test_legacy_panel_renders_score_list() -> None:
    legacy1 = LegacyScore(
        ending_kind=EndingKind.BANKRUPTCY,
        ending_year=2,
        ending_cash_cents=-30_000_00,
        total_fans=50,
        games_shipped=1,
        mega_hits=0,
    )
    legacy2 = LegacyScore(
        ending_kind=EndingKind.MEGA_HIT,
        ending_year=5,
        ending_cash_cents=200_000_00,
        total_fans=1000,
        games_shipped=3,
        mega_hits=2,
    )
    panel = LegacyPanel([legacy1, legacy2])
    text = panel.render()
    assert "Legacy (2)" in text
    assert "BANKRUPTCY" in text
    assert "MEGA_HIT" in text
    assert "Year 2" in text
    assert "Year 5" in text


def test_legacy_panel_empty_state() -> None:
    panel = LegacyPanel(())
    text = panel.render()
    assert "no endings yet" in text


def test_legacy_panel_rendered_as_static_when_app_has_legacy_scores() -> None:
    """When the App has legacy scores in state, the body should show them.

    The App integration lives in Phase 2G T8 — here we just verify the
    render() output is suitable for SVG grep.
    """
    legacy = LegacyScore(
        ending_kind=EndingKind.MEGA_HIT,
        ending_year=5,
        ending_cash_cents=200_000_00,
        total_fans=1000,
        games_shipped=3,
        mega_hits=2,
    )
    panel = LegacyPanel([legacy])
    text = panel.render()
    assert "Legacy (1)" in text
    assert "MEGA_HIT" in text
    assert "Year 5" in text


def test_ending_kind_labels_complete() -> None:
    assert set(ENDING_LABELS.keys()) == set(EndingKind)
    for kind in EndingKind:
        assert isinstance(ENDING_LABELS[kind], str)
        assert len(ENDING_LABELS[kind]) > 0
