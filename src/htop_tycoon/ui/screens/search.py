"""SearchScreen — F3 key: 직원 이름 검색."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static
from htop_tycoon.ui.i18n import bind_en_ko


def render_search_text(query: str = "", candidates: list[str] | None = None) -> str:
    """Pure function returning SearchScreen body Korean text."""
    cands = list(candidates) if candidates else []
    lines: list[str] = [
        "=== 직원 검색 ===",
        "",
        f"검색: {query}",
        "",
    ]
    if not cands:
        lines.append("(검색 결과 없음 — Esc로 닫기)")
    else:
        lines.append(f"결과 {len(cands)}건:")
        for c in cands:
            lines.append(f"  • {c}")
        lines.append("")
        lines.append("직원을 선택하면 OrgTree에서 강조됩니다.")
    lines.append("[닫기: Esc]")
    return "\n".join(lines)


class SearchScreen(ModalScreen[None]):
    """검색 모달. Esc로 닫기."""

    BINDINGS = [
        *bind_en_ko("escape", "app.close_top_modal", "닫기", show=True),
        *bind_en_ko("0", "app.digit('0')", "정지", show=True),
        *bind_en_ko("1", "app.digit('1')", "1x", show=True),
        *bind_en_ko("2", "app.digit('2')", "2x", show=True),
        *bind_en_ko("3", "app.digit('3')", "3x", show=True),
        *bind_en_ko("4", "app.digit('4')", "4x", show=True),
    ]

    DEFAULT_CSS = """
    SearchScreen {
        layer: modal;
        align: center middle;
    }
    #search-content {
        width: 70;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def __init__(self, query: str = "", candidates: list[str] | None = None) -> None:
        super().__init__()
        self._search_query = query
        self._candidates: list[str] = list(candidates) if candidates else []

    @property
    def query_text(self) -> str:
        return self._search_query

    @property
    def candidates(self) -> list[str]:
        return list(self._candidates)

    def compose(self) -> ComposeResult:
        yield Static(
            render_search_text(self._search_query, self._candidates),
            id="search-content",
        )
