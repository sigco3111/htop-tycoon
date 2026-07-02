"""ReleaseScreen modal — show shipped projects to release."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.domain import CompanyState, GameProject, ProjectId
from htop_tycoon.ui.i18n import GENRE_KO


def render_release_text(projects: list[GameProject]) -> str:
    """Pure function returning ReleaseScreen body Korean text."""
    if not projects:
        return (
            "출시: 출시 가능한 프로젝트가 없습니다.\n"
            "먼저 프로젝트를 완성하세요 (진척도 100%)."
        )
    lines = [f"출시 (1-{len(projects)} 선택)", ""]
    for idx, p in enumerate(projects, start=1):
        genre_ko = GENRE_KO.get(p.genre.value, p.genre.value)
        lines.append(
            f"{idx}. {str(p.title):<20} {genre_ko:<10} "
            f"품질:{p.quality.sum()}/400 개발일:{p.days_in_dev}"
        )
    lines.append("")
    lines.append(f"1-{len(projects)} 키로 출시, 'esc'로 취소.")
    return "\n".join(lines)


class ReleaseScreen(ModalScreen[None]):
    """출시 모달. Esc로 닫기."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "닫기"),
        Binding("0", "app.digit('0')", "정지"),
        Binding("1", "app.digit('1')", "1"),
        Binding("2", "app.digit('2')", "2"),
        Binding("3", "app.digit('3')", "3"),
        Binding("4", "app.digit('4')", "4"),
        Binding("5", "app.digit('5')", "5"),
        Binding("6", "app.digit('6')", "6"),
        Binding("7", "app.digit('7')", "7"),
        Binding("8", "app.digit('8')", "8"),
        Binding("9", "app.digit('9')", "9"),
    ]

    DEFAULT_CSS = """
    ReleaseScreen {
        layer: modal;
        align: center middle;
    }
    #release-content {
        width: 80;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def __init__(self, state: CompanyState) -> None:
        super().__init__()
        self._state = state
        self._projects: list[GameProject] = [p for p in state.projects.values() if p.is_shipped]

    @property
    def projects(self) -> tuple[GameProject, ...]:
        return tuple(self._projects)

    def compose(self) -> ComposeResult:
        yield Static(render_release_text(self._projects), id="release-content")

    def select(self, idx: int) -> ProjectId | None:
        if 1 <= idx <= len(self._projects):
            return self._projects[idx - 1].id
        return None

