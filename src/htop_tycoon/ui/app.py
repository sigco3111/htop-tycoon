"""HtopTycoonApp — root Textual application.

Phase 2G: engine tick + speed control + save/load + ending detection.
Key bindings 0/1/2/3/4 set speed, p toggles pause, q quits,
f2 saves, f9 loads, F10 requests voluntary sale. State is injected
(defaults to mock_state); rng defaults to seeded GameRng.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Static

from htop_tycoon.domain import CompanyState
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine import (
    DEFAULT_MARKET,
    HARD_ENDINGS,
    MarketState,
    construct_legacy_score,
    detect_ending,
    record_ending,
    tick,
)
from htop_tycoon.persistence import SAVE_PATH, load_state, save_state
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.ending import EndingScreen, LegacyPanel
from htop_tycoon.ui.theme import HtopTycoonTheme
from htop_tycoon.ui.widgets.footer import Footer as HtopFooter
from htop_tycoon.ui.widgets.header import Header as HtopHeader
from htop_tycoon.ui.widgets.metric_bar import MetricBar
from htop_tycoon.ui.widgets.org_tree import OrgTree

if TYPE_CHECKING:
    from textual.timer import Timer as Interval  # alias for readability


class HtopTycoonApp(App[int]):
    """Root app for the htop-tycoon v3.0 TUI.

    Phase 2G surfaces:
    - Terminal-green theme registered + selected.
    - Header / OrgTree / MetricBar / LegacyPanel / Footer mounted, driven by state.
    - Timer advances state by one day per interval (speed-dependent).
    - BINDINGS for speed (0/1/2/3/4), pause toggle (p), save (f2),
      load (f9), sell (F10), quit (q).
    - Hard ending detection pauses the timer + pushes EndingScreen modal.
    """

    TITLE: str = "htop-tycoon v3.0"
    SUB_TITLE: str = "Kairosoft Game Dev Story — htop edition"

    BINDINGS = [
        Binding("0", "set_speed(0)", "Pause", show=True),
        Binding("1", "set_speed(1)", "1x", show=True),
        Binding("2", "set_speed(2)", "2x", show=True),
        Binding("3", "set_speed(3)", "3x", show=True),
        Binding("4", "set_speed(4)", "4x headless", show=True),
        Binding("p", "toggle_pause", "Pause toggle", show=True),
        Binding("f2", "save_game", "Save", show=True),
        Binding("f9", "load_game", "Load", show=True),
        Binding("f10", "request_sell", "Sell studio", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        state: CompanyState | None = None,
        rng: GameRng | None = None,
        market: MarketState | None = None,
        save_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.register_theme(HtopTycoonTheme())
        self.theme = HtopTycoonTheme().name
        self._state: CompanyState = state if state is not None else mock_state()
        self._rng: GameRng = rng if rng is not None else GameRng(self._state.rng_seed)
        self._market: MarketState = market if market is not None else DEFAULT_MARKET
        self._save_path: Path = save_path if save_path is not None else SAVE_PATH
        self._tick_interval: Interval | None = None
        self._tick_count: int = 0
        self._pending_ending_screen: EndingScreen | None = None

    def compose(self) -> ComposeResult:
        yield HtopHeader(state=self._state)
        with Vertical(id="body"):
            yield OrgTree(self._state)
            yield MetricBar(self._state)
            yield Static(LegacyPanel(self._state.legacy_scores).render())
        yield HtopFooter()

    def _refresh_header(self) -> None:
        old = self.query(HtopHeader)
        for h in list(old):
            h.remove()
        self.mount(HtopHeader(state=self._state), before=0)

    def _refresh_legacy(self) -> None:
        legacy = self.query("Static")[-1]  # last Static in body
        if hasattr(legacy, "update"):
            legacy.update(LegacyPanel(self._state.legacy_scores).render())

    def on_mount(self) -> None:
        self._restart_timer()

    def on_unmount(self) -> None:
        if self._tick_interval is not None:
            self._tick_interval.stop()
            self._tick_interval = None

    def _restart_timer(self) -> None:
        if self._tick_interval is not None:
            self._tick_interval.stop()
            self._tick_interval = None
        if self._state.speed > 0:
            interval_seconds = 1.0 / self._state.speed
            self._tick_interval = self.set_interval(
                interval_seconds,
                self._advance_one_tick,
                name="tick",
            )

    def _advance_one_tick(self) -> None:
        self._state = tick(self._state, self._rng, self._market)
        self._tick_count += 1
        ending = detect_ending(self._state)
        if ending is not None and ending.kind in HARD_ENDINGS:
            self._state = self._state.set_speed(0)
            self._state = record_ending(self._state, ending)
            legacy = construct_legacy_score(self._state, ending)
            self._pending_ending_screen = EndingScreen(ending, legacy)
            self._restart_timer()
        self._refresh_header()
        self._refresh_widgets()

    def _refresh_widgets(self) -> None:
        body = self.query_one("#body", Vertical)
        body.remove_children()
        body.mount(OrgTree(self._state))
        body.mount(MetricBar(self._state))
        body.mount(Static(LegacyPanel(self._state.legacy_scores).render()))

    def action_set_speed(self, speed: int) -> None:
        self._state = self._state.set_speed(speed)
        self._restart_timer()
        self._refresh_widgets()

    def action_toggle_pause(self) -> None:
        new_speed = 0 if self._state.speed > 0 else 1
        self.action_set_speed(new_speed)

    def action_save_game(self) -> None:
        try:
            save_state(self._state, self._save_path)
            self.notify(f"Saved: {self._save_path}")
        except OSError as exc:
            self.notify(f"Save failed: {exc}")

    def action_load_game(self) -> None:
        try:
            self._state = load_state(self._save_path)
        except FileNotFoundError:
            self.notify("No save file")
            return
        except OSError as exc:
            self.notify(f"Load failed: {exc}")
            return
        self._refresh_header()
        self._refresh_widgets()
        self.notify("Loaded")

    def action_request_sell(self) -> None:
        self._state = self._state.set_voluntary_sale_pending(True)
        self.notify("Sell request queued — fires next tick if cash ≥ $200,000")
        self._refresh_widgets()
