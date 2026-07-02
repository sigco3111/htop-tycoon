"""PromoteScreen — F7 key: LEAD 직원 승진."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.domain import CompanyState, Employee, EmployeeId
from htop_tycoon.ui.i18n import DEPT_KO, JOB_KO


def render_promote_text(state: CompanyState) -> str:
    """Pure function returning PromoteScreen body Korean text."""
    threshold = 70
    max_lv = 10
    ordered: list[Employee] = sorted(
        [e for e in state.employees.values() if e.job.value == "LEAD"],
        key=lambda e: (-e.satisfaction, int(e.id)),
    )
    lines: list[str] = ["=== 직원 승진 ===", ""]
    if not ordered:
        lines.append("승진 가능한 LEAD 직원이 없습니다.")
        lines.append("")
        lines.append("[닫기: Esc]")
        return "\n".join(lines)
    lines.append(f"승진 가능 (만족도 {threshold}%+, L{max_lv} 미만):")
    for idx, e in enumerate(ordered, start=1):
        can = e.satisfaction >= threshold and e.level < max_lv
        marker = " ✓ 승진 가능" if can else " (불가)"
        job_ko = JOB_KO.get(e.job.value, e.job.value)
        dept_ko = DEPT_KO.get(e.dept.value, e.dept.value)
        lines.append(
            f"{idx}. {e.name:<10} {job_ko:<8} L{e.level:<2} "
            f"만족도:{e.satisfaction}% [{dept_ko}]{marker}"
        )
    lines.append("")
    lines.append("1-N 선택하여 승진. 승진 시 레벨 +1, 급여 자동 인상.")
    lines.append("[닫기: Esc]")
    return "\n".join(lines)


class PromoteScreen(ModalScreen[None]):
    """승진 모달. Esc로 닫기."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "닫기"),
        Binding("0", "app.digit('0')", "정지"),
        Binding("1", "app.digit('1')", "1x"),
        Binding("2", "app.digit('2')", "2x"),
        Binding("3", "app.digit('3')", "3x"),
        Binding("4", "app.digit('4')", "4x"),
    ]

    DEFAULT_CSS = """
    PromoteScreen {
        layer: modal;
        align: center middle;
    }
    #promote-content {
        width: 70;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    PROMOTION_SAT_THRESHOLD: int = 70
    MAX_LEVEL: int = 10

    def __init__(self, state: CompanyState) -> None:
        super().__init__()
        self._state = state
        self._ordered: list[Employee] = sorted(
            [e for e in state.employees.values() if e.job.value == "LEAD"],
            key=lambda e: (-e.satisfaction, int(e.id)),
        )

    @property
    def ordered(self) -> list[Employee]:
        return list(self._ordered)

    def compose(self) -> ComposeResult:
        yield Static(render_promote_text(self._state), id="promote-content")

    def select(self, idx: int) -> EmployeeId | None:
        if 1 <= idx <= len(self._ordered):
            return self._ordered[idx - 1].id
        return None
