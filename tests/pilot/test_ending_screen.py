"""T7 pilot: EndingScreen + LegacyPanel render."""

from __future__ import annotations

from htop_tycoon.engine.endings import Ending, EndingKind, LegacyScore
from htop_tycoon.ui.screens.ending import (
    ENDING_LABELS,
    LegacyPanel,
    render_ending_text,
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
    text = render_ending_text(ending, legacy)
    assert "파산" in text
    assert "3년차" in text
    assert "-$55,000" in text
    assert "팬: 120" in text
    assert "출시 게임: 4" in text
    assert "메가히트: 1" in text
    assert "[새 게임]" in text
    assert "[종료]" in text


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
    assert "레거시 (2)" in text
    assert "파산" in text
    assert "대박" in text
    assert "2년차" in text
    assert "5년차" in text


def test_legacy_panel_empty_state() -> None:
    panel = LegacyPanel(())
    text = panel.render()
    assert "아직 엔딩 없음" in text


def test_legacy_panel_rendered_as_static_when_app_has_legacy_scores() -> None:
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
    assert "레거시 (1)" in text
    assert "대박" in text
    assert "5년차" in text


def test_ending_kind_labels_complete() -> None:
    assert set(ENDING_LABELS.keys()) == set(EndingKind)
    for kind in EndingKind:
        assert isinstance(ENDING_LABELS[kind], str)
        assert len(ENDING_LABELS[kind]) > 0
