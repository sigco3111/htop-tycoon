"""ConsoleMarketScreen modal — show purchasable consoles."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.domain import CompanyState, Console
from htop_tycoon.engine.console_market import (
    available_consoles,
    console_price,
)


def render_console_market_text(state: CompanyState, listings: list[Console]) -> str:
    """Pure function returning ConsoleMarketScreen body Korean text."""
    lines = ["콘솔 마켓", ""]
    if state.own_console is not None:
        lines.append(f"보유 중: {state.own_console.value}")
    else:
        lines.append("보유 중: (없음)")
    lines.append(f"현금: {state.cash}")
    lines.append("")
    if not listings:
        lines.append("구매 가능한 콘솔이 없습니다.")
    else:
        lines.append("구매 가능:")
        for idx, console in enumerate(listings, start=1):
            price = console_price(console)
            lines.append(f"  {idx}. {console.value:<12} {price}")
    lines.append("")
    lines.append(f"1-{len(listings)} 키로 구매, 'c'로 닫기.")
    return "\n".join(lines)


class ConsoleMarketScreen(ModalScreen[None]):
    """콘솔 마켓 모달. Esc로 닫기."""

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
    ConsoleMarketScreen {
        layer: modal;
        align: center middle;
    }
    #console-content {
        width: 70;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def __init__(self, state: CompanyState) -> None:
        super().__init__()
        self._state = state
        owned = state.own_console
        self._listings: list[Console] = [
            c for c in available_consoles() if c != owned
        ]

    @property
    def listings(self) -> tuple[Console, ...]:
        return tuple(self._listings)

    def compose(self) -> ComposeResult:
        yield Static(
            render_console_market_text(self._state, self._listings),
            id="console-content",
        )

    def select(self, idx: int) -> Console | None:
        if 1 <= idx <= len(self._listings):
            return self._listings[idx - 1]
        return None

