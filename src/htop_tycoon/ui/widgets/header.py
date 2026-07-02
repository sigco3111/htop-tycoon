"""Header — top htop-style status bar.

Phase 1: renders mock game state (Year, Cash, Fans, Strategy) in a horizontal
strip. Phase 2+ will bind these to live State from the engine.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

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

    def compose(self) -> ComposeResult:
        """Yield four Static widgets with mock game state labels."""
        yield Static(MOCK_YEAR, id="hdr-year")
        yield Static(MOCK_CASH, id="hdr-cash")
        yield Static(MOCK_FANS, id="hdr-fans")
        yield Static(MOCK_STRATEGY, id="hdr-strategy")
