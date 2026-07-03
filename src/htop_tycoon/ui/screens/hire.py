"""HireScreen modal — shows N candidates to hire from."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.engine.hr import HireCandidate
from htop_tycoon.ui.i18n import DEPT_KO, JOB_KO
from htop_tycoon.ui.i18n import bind_en_ko
from htop_tycoon.ui.ime import KoreanIMEMixin


def render_hire_text(candidates: list[HireCandidate]) -> str:
    """Pure function returning HireScreen body Korean text."""
    lines: list[str] = [f"고용 (1-{len(candidates)} 선택)", ""]
    for idx, c in enumerate(candidates, start=1):
        job_ko = JOB_KO.get(c.job.value, c.job.value)
        dept_ko = DEPT_KO.get(c.department.value, c.department.value)
        lines.append(
            f"{idx}. {c.name:<10} {job_ko:<14} L{c.suggested_level:<2} "
            f"{dept_ko:<6} {c.monthly_salary}/월"
        )
    lines.append("")
    lines.append(f"1-{len(candidates)} 키로 고용, 'h'로 닫기.")
    return "\n".join(lines)

class HireScreen(KoreanIMEMixin, ModalScreen[None]):
    """고용 모달. Esc로 닫기."""

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
    HireScreen {
        layer: modal;
        align: center middle;
    }
    #hire-content {
        width: 80;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def __init__(self, candidates: list[HireCandidate]) -> None:
        super().__init__()
        self._candidates: list[HireCandidate] = list(candidates)

    @property
    def candidates(self) -> list[HireCandidate]:
        return list(self._candidates)

    def compose(self) -> ComposeResult:
        yield Static(render_hire_text(self._candidates), id="hire-content")

    def select(self, idx: int) -> HireCandidate | None:
        if 1 <= idx <= len(self._candidates):
            return self._candidates[idx - 1]
        return None

