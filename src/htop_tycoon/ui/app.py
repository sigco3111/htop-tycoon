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
from htop_tycoon.domain.enums import Console, StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine import (
    DEFAULT_MARKET,
    HARD_ENDINGS,
    MarketState,
    construct_legacy_score,
    detect_ending,
    fire_employee,
    generate_candidates,
    hire_employee,
    purchase_console,
    record_ending,
    release_project,
    tick,
)
from htop_tycoon.persistence import SAVE_PATH, load_state, save_state
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.console import ConsoleMarketScreen
from htop_tycoon.ui.screens.ending import EndingScreen, LegacyPanel
from htop_tycoon.ui.screens.fire import FireScreen
from htop_tycoon.ui.screens.hire import HireScreen
from htop_tycoon.ui.screens.release import ReleaseScreen
from htop_tycoon.ui.screens.strategy_picker import StrategyPicker
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
        Binding("s", "open_strategy_picker", "Strategy", show=True),
        Binding("1", "select_strategy('AGGRESSIVE')", "1.Aggr", show=False),
        Binding("2", "select_strategy('CONSERVATIVE')", "2.Cons", show=False),
        Binding("3", "select_strategy('BALANCED')", "3.Bal", show=False),
        Binding("4", "select_strategy('GENRE_FOCUS')", "4.Focus", show=False),
        Binding("h", "open_hire_screen", "Hire", show=True),
        Binding("x", "open_fire_screen", "Fire", show=True),
        Binding("5", "select_candidate('5')", "5.Cand", show=False),
        Binding("6", "select_candidate('6')", "6.Cand", show=False),
        Binding("7", "select_candidate('7')", "7.Cand", show=False),
        Binding("8", "select_candidate('8')", "8.Cand", show=False),
        Binding("9", "select_fire_target('9')", "9.Fire", show=False),
        Binding("0", "select_release_target('0')", "0.Rel", show=False),
        Binding("c", "open_console_market", "Console", show=True),
        Binding("0", "buy_console('0')", "0.Cons", show=False),
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
        self._pending_strategy_picker: StrategyPicker | None = None
        self._pending_hire_screen: HireScreen | None = None
        self._pending_fire_screen: FireScreen | None = None
        self._pending_release_screen: ReleaseScreen | None = None
        self._pending_console_screen: ConsoleMarketScreen | None = None
        self._pending_release_target: Console | None = None

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

    def action_open_strategy_picker(self) -> None:
        self._pending_strategy_picker = StrategyPicker(self._state.strategy)
        self.notify(
            f"Strategy picker (current: {self._state.strategy.value}). Press 1-4 to change."
        )

    def action_select_strategy(self, kind_str: str) -> None:
        kind = StrategyKind(kind_str)
        self._state = self._state.set_strategy(kind)
        self.notify(f"Strategy: {kind.value}")
        self._refresh_header()
        self._refresh_widgets()

    def action_open_hire_screen(self) -> None:
        used = {e.name for e in self._state.employees.values()}
        self._pending_hire_screen = HireScreen(
            generate_candidates(self._rng, count=5, used_names=used)
        )
        self.notify(f"Hire: {len(self._pending_hire_screen.candidates)} candidates")

    def action_select_candidate(self, idx_str: str) -> None:
        if self._pending_hire_screen is None:
            return
        candidate = self._pending_hire_screen.select(int(idx_str))
        if candidate is None:
            self.notify("Invalid selection")
            return
        self._state = hire_employee(self._state, candidate)
        self.notify(f"Hired: {candidate.name} ({candidate.job.value} L{candidate.suggested_level})")
        self._pending_hire_screen = None
        self._refresh_header()
        self._refresh_widgets()

    def action_open_fire_screen(self) -> None:
        if not self._state.employees:
            self.notify("No employees to fire")
            return
        self._pending_fire_screen = FireScreen(self._state)
        self.notify("Fire: pick employee to terminate")

    def action_select_fire_target(self, idx_str: str) -> None:
        if self._pending_fire_screen is None:
            return
        target_id = self._pending_fire_screen.select(int(idx_str))
        if target_id is None:
            self.notify("Invalid selection")
            return
        emp_name = self._state.employees[target_id].name
        self._state = fire_employee(self._state, target_id)
        self.notify(f"Fired: {emp_name}")
        self._pending_fire_screen = None
        self._refresh_header()
        self._refresh_widgets()

    def action_open_release_screen(self) -> None:
        self._pending_release_screen = ReleaseScreen(self._state)
        if not self._pending_release_screen.projects:
            self.notify("No shipped projects to release")

    def action_select_release_target(self, idx_str: str) -> None:
        if self._pending_release_screen is None:
            return
        project_id = self._pending_release_screen.select(int(idx_str))
        if project_id is None:
            self.notify("Invalid selection")
            return
        from htop_tycoon.engine.console_market import available_consoles

        target = next(
            (c for c in available_consoles() if c != self._state.own_console),
            None,
        )
        if target is None:
            self.notify("No available console to release on")
            return
        try:
            self._state = release_project(
                self._state, project_id, target, self._market, self._rng
            )
            self.notify(f"Released on {target.value}")
        except ValueError as exc:
            self.notify(f"Release failed: {exc}")
            return
        self._pending_release_screen = None
        self._refresh_header()
        self._refresh_widgets()

    def action_open_console_market(self) -> None:
        self._pending_console_screen = ConsoleMarketScreen(self._state)

    def action_buy_console(self, idx_str: str) -> None:
        if self._pending_console_screen is None:
            return
        console = self._pending_console_screen.select(int(idx_str))
        if console is None:
            self.notify("Invalid selection")
            return
        try:
            self._state = purchase_console(self._state, console)
            self.notify(f"Purchased: {console.value}")
        except ValueError as exc:
            self.notify(f"Purchase failed: {exc}")
            return
        self._pending_console_screen = None
        self._refresh_header()
        self._refresh_widgets()
