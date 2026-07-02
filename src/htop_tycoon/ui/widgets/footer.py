"""Footer — bottom htop-style hint bar.

Phase 1: renders the 6 F-key hints (KO), 4 secondary key hints, and a
status strip (Speed / Auto). Phase 2+ will wire key bindings to a registry.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

F_KEY_HINTS: tuple[str, ...] = (
    "F1도움",
    "F2저장",
    "F3검색",
    "F5트리",
    "F7승진",
    "F9해고",
)

SECONDARY_KEY_HINTS: tuple[str, ...] = (
    "H고용",
    "n새게임",
    "s전략",
    "d자동",
)

MOCK_SPEED_LABEL: str = "Speed 1x"
MOCK_AUTO_LABEL: str = "Auto OFF"


class Footer(Horizontal):
    """htop-style bottom bar with F-key hints, secondary keys, and status."""

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

    def compose(self) -> ComposeResult:
        """Yield four Static widgets: F-keys, secondary, speed, auto."""
        yield Static(" ".join(F_KEY_HINTS))
        yield Static(" ".join(SECONDARY_KEY_HINTS))
        yield Static(MOCK_SPEED_LABEL)
        yield Static(MOCK_AUTO_LABEL)
