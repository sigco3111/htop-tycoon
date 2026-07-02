"""HtopTycoonApp — root Textual application.

Phase 2C: accepts an optional CompanyState. When None, falls back to
mock_state(). Composes Header (with state), OrgTree (with state), and
Footer (no state). Domain/engine wiring lands in later phases.
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from htop_tycoon.domain import CompanyState
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.theme import HtopTycoonTheme
from htop_tycoon.ui.widgets.footer import Footer as HtopFooter
from htop_tycoon.ui.widgets.header import Header as HtopHeader
from htop_tycoon.ui.widgets.org_tree import OrgTree


class HtopTycoonApp(App[int]):
    """Root app for the htop-tycoon v3.0 TUI.

    Phase 2C surfaces:
    - Terminal-green theme registered + selected.
    - Header (Year/Cash/Fans/Strategy) — driven by injected state.
    - OrgTree (dept grouping + employees + zombies) — driven by state.
    - Footer (F-key hints + Speed/Auto status) — static for now.
    """

    TITLE: str = "htop-tycoon v3.0"
    SUB_TITLE: str = "Kairosoft Game Dev Story — htop edition"

    def __init__(self, state: CompanyState | None = None) -> None:
        super().__init__()
        self.register_theme(HtopTycoonTheme())
        self.theme = HtopTycoonTheme().name
        self._state: CompanyState = state if state is not None else mock_state()

    def compose(self) -> ComposeResult:
        yield HtopHeader(state=self._state)
        yield OrgTree(self._state)
        yield HtopFooter()
