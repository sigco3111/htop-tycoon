"""StrategyPicker — modal screen for selecting one of 4 strategies."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.ui.i18n import STRATEGY_KO

STRATEGY_DESCRIPTIONS: dict[StrategyKind, str] = {
    StrategyKind.AGGRESSIVE: "공격적 고용, 큰 프로젝트, 위험 감수",
    StrategyKind.CONSERVATIVE: "신중, 현금 부족시 정리",
    StrategyKind.BALANCED: "중간 규모 채용, 다양한 장르",
    StrategyKind.GENRE_FOCUS: "한 장르에 집중하여 깊이 개발",
}


def render_strategy_picker_text(current: StrategyKind) -> str:
    all_kinds = list(StrategyKind)
    current_ko = STRATEGY_KO.get(current.value, current.value)
    lines = [
        f"전략: → {current_ko} ←",
        "",
    ]
    for idx, kind in enumerate(all_kinds, start=1):
        ko_name = STRATEGY_KO.get(kind.value, kind.value)
        desc = STRATEGY_DESCRIPTIONS[kind]
        lines.append(f"{idx}. {ko_name:<10} - {desc}")
    lines.append("")
    lines.append("1-4 키로 선택, 's'로 닫기, 'esc'로 취소.")
    return "\n".join(lines)


class StrategyPicker(ModalScreen[None]):
    """전략 선택 모달. Esc로 닫기."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "닫기"),
        Binding("0", "app.digit('0')", "정지"),
        Binding("1", "app.digit('1')", "1x"),
        Binding("2", "app.digit('2')", "2x"),
        Binding("3", "app.digit('3')", "3x"),
        Binding("4", "app.digit('4')", "4x"),
    ]

    DEFAULT_CSS = """
    StrategyPicker {
        layer: modal;
        align: center middle;
    }
    #strategy-picker-content {
        width: 70;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def __init__(self, current: StrategyKind) -> None:
        super().__init__()
        self._current = current

    @property
    def current(self) -> StrategyKind:
        return self._current

    def compose(self) -> ComposeResult:
        yield Static(
            render_strategy_picker_text(self._current),
            id="strategy-picker-content",
        )

    def select(self, kind: StrategyKind) -> StrategyKind:
        return kind

