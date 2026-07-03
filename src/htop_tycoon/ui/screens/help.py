"""HelpScreen — F1 key: 모든 키 바인딩 + 전략 + 엔딩을 한글로 표시."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.ui.i18n import BINDINGS_KO, ENDING_KO, SET_KO_LABELS
from htop_tycoon.ui.i18n import bind_en_ko


def render_help_text() -> str:
    """Pure function returning HelpScreen body Korean text."""
    lines: list[str] = [
        "=== htop-tycoon v3.0 도움말 ===",
        "",
        "[ F-키 ]",
        f"F1  {BINDINGS_KO['f1']:<8}  F2  {BINDINGS_KO['f2']:<8}  F3  {BINDINGS_KO['f3']:<8}",
        f"F5  {BINDINGS_KO['f5']:<8}  F7  {BINDINGS_KO['f7']:<8}  F8  {BINDINGS_KO['f8']:<8}",
        f"F9  {BINDINGS_KO['f9']:<8}  F10 매각",
        "",
        "[ 단축키 ]",
        "s   전략 선택    h   신규 고용    x   (legacy 해고)",
        "n   새 게임      d   자동 ON/OFF  c   콘솔 마켓",
        "p   일시정지     q   종료",
        "0   정지         1-4 속도 (1x/2x/3x/4x)",
        "Space 직원 태그 (placeholder)",
        "",
        "[ 전략 ]",
        f"1. {SET_KO_LABELS['AGGRESSIVE']:<10} - 공격적 고용, 큰 프로젝트, 위험 감수",
        f"2. {SET_KO_LABELS['CONSERVATIVE']:<10} - 신중, 현금 부족시 정리",
        f"3. {SET_KO_LABELS['BALANCED']:<10} - 중간 규모 채용, 다양한 장르",
        f"4. {SET_KO_LABELS['GENRE_FOCUS']:<10} - 한 장르 집중 개발",
        "",
        "[ 엔딩 ]",
        f"• {ENDING_KO['BANKRUPTCY']:<10} - 현금 -$50,000 이하",
        f"• {ENDING_KO['VOLUNTARY_SALE']:<10} - F10 매각 (현금 $200,000+)",
        f"• {ENDING_KO['MEGA_HIT']:<10} - 단일 게임 100만+ 판매",
        f"• {ENDING_KO['HALL_OF_FAME']:<10} - 5개+ 명예의 전당",
        f"• {ENDING_KO['SECRET']:<10} - 자사 콘솔 + 100만 판매",
        "",
        "속도: 1x = 1초 = 1게임일. 일시정지 = p 또는 0.",
        "[닫기: Esc]",
    ]
    return "\n".join(lines)


class HelpScreen(ModalScreen[None]):
    """도움말 모달. Esc로 닫기."""

    BINDINGS = [
        *bind_en_ko("escape", "app.close_top_modal", "닫기", show=True),
        *bind_en_ko("0", "app.digit('0')", "정지", show=True),
        *bind_en_ko("1", "app.digit('1')", "1x", show=True),
        *bind_en_ko("2", "app.digit('2')", "2x", show=True),
        *bind_en_ko("3", "app.digit('3')", "3x", show=True),
        *bind_en_ko("4", "app.digit('4')", "4x", show=True),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        layer: modal;
        align: center middle;
    }
    #help-content {
        width: 90;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(render_help_text(), id="help-content")
