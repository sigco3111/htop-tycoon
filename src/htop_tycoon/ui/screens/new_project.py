"""NewProjectScreen — 'n' key: 새 게임 프로젝트 시작 (장르 선택)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.domain.enums import Genre
from htop_tycoon.ui.i18n import GENRE_KO
from htop_tycoon.ui.i18n import bind_en_ko


def render_new_project_text(genres: list[Genre] | None = None) -> str:
    """Pure function returning NewProjectScreen body Korean text."""
    genre_list: list[Genre] = list(genres) if genres else list(Genre)
    lines: list[str] = [
        "=== 새 게임 프로젝트 ===",
        "",
        f"장르 선택 (1-{len(genre_list)}):",
        "",
    ]
    for idx, genre in enumerate(genre_list, start=1):
        ko_name = GENRE_KO.get(genre.value, genre.value)
        lines.append(f"{idx}. {ko_name}")
    lines.append("")
    lines.append("장르 번호를 눌러 새 프로젝트를 시작하세요.")
    lines.append("[닫기: Esc]")
    return "\n".join(lines)


class NewProjectScreen(ModalScreen[None]):
    """새 프로젝트 모달. Esc로 닫기."""

    BINDINGS = [
        *bind_en_ko("escape", "app.close_top_modal", "닫기", show=True),
        *bind_en_ko("0", "app.digit('0')", "정지", show=True),
        *bind_en_ko("1", "app.digit('1')", "1x", show=True),
        *bind_en_ko("2", "app.digit('2')", "2x", show=True),
        *bind_en_ko("3", "app.digit('3')", "3x", show=True),
        *bind_en_ko("4", "app.digit('4')", "4x", show=True),
    ]

    DEFAULT_CSS = """
    NewProjectScreen {
        layer: modal;
        align: center middle;
    }
    #new-project-content {
        width: 60;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def __init__(self, genres: list[Genre] | None = None) -> None:
        super().__init__()
        self._genres: list[Genre] = list(genres) if genres else list(Genre)

    @property
    def genres(self) -> tuple[Genre, ...]:
        return tuple(self._genres)

    def compose(self) -> ComposeResult:
        yield Static(
            render_new_project_text(self._genres),
            id="new-project-content",
        )
