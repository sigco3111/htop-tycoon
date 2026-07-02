"""Footer — bottom htop-style hint bar with live speed/auto indicators."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from htop_tycoon.domain import CompanyState

F_KEY_HINTS: tuple[str, ...] = (
    "F1도움",
    "F2저장",
    "F3검색",
    "F5트리",
    "F7승진",
    "F8로드",
    "F9해고",
)

SECONDARY_KEY_HINTS: tuple[str, ...] = (
    "H고용",
    "n새게임",
    "s전략",
    "d자동",
)

SPEED_LABEL_ID: str = "footer-speed"
AUTO_LABEL_ID: str = "footer-auto"


def _speed_label(speed: int) -> str:
    if speed == 0:
        return "속도 정지"
    return f"속도 {speed}x"


def _auto_label(auto_on: bool) -> str:
    return "자동 ON" if auto_on else "자동 OFF"


class Footer(Horizontal):
    """htop-style bottom bar with F-key hints, secondary keys, and live status."""

    DEFAULT_CSS: ClassVar[str] = """
    Footer {
        height: 1;
        background: $background;
        color: $primary;
        padding: 0 1;
    }

    Footer Static {
        width: auto;
        padding: 0 1;
    }
    """

    def __init__(self, state: CompanyState | None = None) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        """Yield four Static widgets: F-keys, secondary, speed, auto."""
        yield Static(" ".join(F_KEY_HINTS))
        yield Static(" ".join(SECONDARY_KEY_HINTS))
        speed = self._state.speed if self._state is not None else 0
        yield Static(_speed_label(speed), id=SPEED_LABEL_ID)
        auto = self._state.auto_on if self._state is not None else False
        yield Static(_auto_label(auto), id=AUTO_LABEL_ID)

    def update_status(self, state: CompanyState) -> None:
        """Refresh live speed/auto labels from current state."""
        self._state = state
        speed_widget = self.query_one(f"#{SPEED_LABEL_ID}", Static)
        speed_widget.update(_speed_label(state.speed))
        auto_widget = self.query_one(f"#{AUTO_LABEL_ID}", Static)
        auto_widget.update(_auto_label(state.auto_on))
