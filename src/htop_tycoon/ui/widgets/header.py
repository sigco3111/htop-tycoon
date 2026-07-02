"""Header — top htop-style status bar.

Phase 2C: accepts an optional CompanyState. When None, renders the
Phase 1 mock data (Year 1, Cash $100,000, etc.). When provided, renders
live values from the state.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from htop_tycoon.domain import CompanyState

MOCK_YEAR: str = "Year 1"
MOCK_CASH: str = "Cash $100,000"
MOCK_FANS: str = "Fans 0"
MOCK_STRATEGY: str = "Strategy: Balanced"


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
        super().__init__(id="header")
        self._state = state

    def compose(self) -> ComposeResult:
        if self._state is None:
            yield Static(MOCK_YEAR, id="hdr-year")
            yield Static(MOCK_CASH, id="hdr-cash")
            yield Static(MOCK_FANS, id="hdr-fans")
            yield Static(MOCK_STRATEGY, id="hdr-strategy")
        else:
            yield Static(f"Year {self._state.year}", id="hdr-year")
            yield Static(f"Cash {self._state.cash}", id="hdr-cash")
            yield Static(f"Fans {self._state.fans}", id="hdr-fans")
            yield Static(
                f"Strategy: {self._state.strategy.value.title()}",
                id="hdr-strategy",
            )
