"""Header — top htop-style status bar."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from htop_tycoon.domain import CompanyState
from htop_tycoon.ui.i18n import STRATEGY_KO

MOCK_YEAR: str = "1년차"
MOCK_CASH: str = "자금 $100,000"
MOCK_FANS: str = "팬 0명"
MOCK_STRATEGY: str = "전략: 균형"


class Header(Horizontal):
    """htop-style top bar with year/cash/fans/strategy."""

    DEFAULT_CSS: ClassVar[str] = """
    Header {
        height: 1;
        background: $background;
        color: $primary;
        padding: 0 1;
    }

    Header Static {
        width: auto;
        padding: 0 1;
    }
    """

    def __init__(self, state: CompanyState | None = None) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        if self._state is None:
            yield Static(MOCK_YEAR, id="hdr-year")
            yield Static(MOCK_CASH, id="hdr-cash")
            yield Static(MOCK_FANS, id="hdr-fans")
            yield Static(MOCK_STRATEGY, id="hdr-strategy")
        else:
            yield Static(f"{self._state.year}년차", id="hdr-year")
            yield Static(f"자금 {self._state.cash}", id="hdr-cash")
            yield Static(f"팬 {self._state.fans:,}명", id="hdr-fans")
            yield Static(
                f"전략: {STRATEGY_KO.get(self._state.strategy.value, self._state.strategy.value)}",
                id="hdr-strategy",
            )

