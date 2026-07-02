"""HtopTycoonApp — root Textual application.

Phase 1: minimal app that registers the terminal-green theme and mounts the
Header + Footer chrome. Body content (OrgTree, MetricBar) lands in Phase 2.
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from htop_tycoon.ui.theme import HtopTycoonTheme
from htop_tycoon.ui.widgets.footer import Footer as HtopFooter
from htop_tycoon.ui.widgets.header import Header as HtopHeader


class HtopTycoonApp(App[int]):
    """Root app for the htop-tycoon v3.0 TUI.

    Phase 1 surfaces:
    - Terminal-green theme registered + selected.
    - Header (Year/Cash/Fans/Strategy mock data) rendered at top.
    - Footer (F-key hints + Speed/Auto status) rendered at bottom.
    """

    TITLE: str = "htop-tycoon v3.0"
    SUB_TITLE: str = "Kairosoft Game Dev Story — htop edition"

    def __init__(self) -> None:
        super().__init__()
        # Register + select theme BEFORE compose() runs so widgets inherit it.
        self.register_theme(HtopTycoonTheme())
        self.theme = HtopTycoonTheme().name

    def compose(self) -> ComposeResult:
        yield HtopHeader()
        yield HtopFooter()
