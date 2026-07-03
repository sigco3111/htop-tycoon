"""FireScreen modal — shows current employees sorted by lowest satisfaction."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.domain import CompanyState, Employee, EmployeeId
from htop_tycoon.ui.i18n import JOB_KO
from htop_tycoon.ui.i18n import bind_en_ko
from htop_tycoon.ui.ime import KoreanIMEMixin


def render_fire_text(ordered: list[Employee], max_visible: int = 9) -> str:
    """Pure function returning FireScreen body Korean text."""
    visible = ordered[:max_visible]
    lines = [f"해고 (1-{len(visible)} 선택, 만족도 낮은 순)", ""]
    for idx, e in enumerate(visible, start=1):
        zombie = " [좀비]" if e.is_zombie else ""
        job_ko = JOB_KO.get(e.job.value, e.job.value)
        lines.append(
            f"{idx}. {e.name:<10} {job_ko:<14} L{e.level:<2} "
            f"만족도:{e.satisfaction}%{zombie}"
        )
    lines.append("")
    lines.append(f"1-{len(visible)} 키로 해고, 'x' 또는 F9로 닫기.")
    return "\n".join(lines)

class FireScreen(KoreanIMEMixin, ModalScreen[None]):
    """해고 모달. Esc로 닫기."""

    BINDINGS = [
        *bind_en_ko("escape", "app.close_top_modal", "닫기", show=True),
        *bind_en_ko("0", "app.digit('0')", "정지", show=True),
        *bind_en_ko("1", "app.digit('1')", "1", show=True),
        *bind_en_ko("2", "app.digit('2')", "2", show=True),
        *bind_en_ko("3", "app.digit('3')", "3", show=True),
        *bind_en_ko("4", "app.digit('4')", "4", show=True),
        *bind_en_ko("5", "app.digit('5')", "5", show=True),
        *bind_en_ko("6", "app.digit('6')", "6", show=True),
        *bind_en_ko("7", "app.digit('7')", "7", show=True),
        *bind_en_ko("8", "app.digit('8')", "8", show=True),
        *bind_en_ko("9", "app.digit('9')", "9", show=True),
    ]

    DEFAULT_CSS = """
    FireScreen {
        layer: modal;
        align: center middle;
    }
    #fire-content {
        width: 70;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    MAX_VISIBLE: int = 9

    def __init__(self, state: CompanyState) -> None:
        super().__init__()
        self._state = state
        self._ordered: list[Employee] = sorted(
            state.employees.values(),
            key=lambda e: (e.satisfaction, int(e.id)),
        )

    @property
    def ordered(self) -> list[Employee]:
        return self._ordered

    def compose(self) -> ComposeResult:
        yield Static(
            render_fire_text(self._ordered, self.MAX_VISIBLE),
            id="fire-content",
        )

    def select(self, idx: int) -> EmployeeId | None:
        if 1 <= idx <= min(len(self._ordered), self.MAX_VISIBLE):
            return self._ordered[idx - 1].id
        return None

