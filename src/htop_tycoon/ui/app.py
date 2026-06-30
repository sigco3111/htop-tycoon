"""htop_tycoon.ui.app — HtopTycoonApp: Textual App skeleton + locked 5-region layout.

Locks the contracts from ``.omo/plans/htop-tycoon.md``:

- T16 (line 434-456): ``HtopTycoonApp`` subclasses ``textual.app.App`` and
  accepts ``seed: int = 42``, ``tick_rate: float = 1.0``, ``no_autosave: bool =
  False``. CSS lives in ``app.tcss`` (sibling of this module) and defines
  the 5 regions plus the header/footer: ``#header``, ``#metrics``, ``#body``
  (containing ``#org-tree`` and ``#employee-panel``), ``#alerts``, ``#footer``.
  ``on_mount`` starts the periodic tick via ``self.set_interval`` using the
  locked wrapper ``self._tick_once``.
- T24 (line 537-561): ``BINDINGS`` extends the F-row with 10 ``Binding``
  objects (F1..F10) registered via ``bindings.registry.register_f_bindings()``.
- T25 (line 565-585): ``BINDINGS`` further extends with 8 single-key
  ``Binding`` objects (t, u, m, p, T, up, down, space) registered via
  ``bindings.registry.register_single_key_bindings()``.
- Wave 7: ``BINDINGS`` further extends with 1 extra single-key binding
  (backtick → toggle_pause) registered via
  ``bindings.registry.register_extra_bindings()``. Total length: 19.

The action handler LOGIC lives in ``ui/action_handlers.py`` (split for the
250 LOC ceiling). This module owns the App lifecycle + layout + state
attributes; each ``action_<name>`` method here is a thin delegation to the
matching handler in ``action_handlers.py``.

This module is the UI entry point. UI handlers MUST NOT mutate ``self.state``
directly — the engine is the only writer (per AGENTS.md "State boundary"
invariant). Each action that returns a new state rebinds ``self.state`` and
publishes the events through ``self.event_bus``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import App
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable

from htop_tycoon.bindings.registry import (
    register_extra_bindings,
    register_f_bindings,
    register_single_key_bindings,
)
from htop_tycoon.data import load_balance
from htop_tycoon.domain.state import EmployeeId, GameState
from htop_tycoon.engine.ai_manager import AutoManager, Decision
from htop_tycoon.engine.events import Event, EventBus, StateUpdated
from htop_tycoon.engine.startup import new_started_game
from htop_tycoon.engine.tick import TickEngine
from htop_tycoon.persistence.serialize import save as persistence_save
from htop_tycoon.ui import action_handlers
from htop_tycoon.ui.app_wiring import (
    promote_bindings_to_priority,
    refresh_widgets_from_state,
    subscribe_focus_events,
    subscribe_regime_events,
)
from htop_tycoon.ui.widgets.alert import Alert
from htop_tycoon.ui.widgets.employee_table import EmployeeTable
from htop_tycoon.ui.widgets.footer import HtopFooter
from htop_tycoon.ui.widgets.header import GameHeader
from htop_tycoon.ui.widgets.metric_bar import MetricBar
from htop_tycoon.ui.widgets.org_tree import OrgTree

if TYPE_CHECKING:
    from textual.timer import Timer


# The CSS file lives next to this module; Textual's default ``CSS_PATH``
# resolution expects a string (or Path) relative to the module.
_CSS_FILE = "app.tcss"

__all__ = ["HtopTycoonApp"]

_logger = logging.getLogger(__name__)


def _default_xdg_save_path() -> Path:
    """Return the locked default save path: ``~/.local/share/htop-tycoon/save.json``.

    Per plan line 646 (XDG Base Directory spec): the user-specific data
    directory ``$XDG_DATA_HOME`` defaults to ``~/.local/share`` on
    Linux. The application's save file lives at
    ``~/.local/share/htop-tycoon/save.json``. Tests override the App's
    ``_save_path`` attribute to point at ``tmp_path`` so the real home
    directory is never touched.
    """
    return Path.home() / ".local" / "share" / "htop-tycoon" / "save.json"


class HtopTycoonApp(App[None]):
    """The htop-tycoon Textual App — 5-region locked layout + locked tick wiring.

    Construction parameters:

    - ``seed`` (default ``42``): RNG seed for ``new_game`` AND ``TickEngine``.
      Same seed must be used for both so the engine's RNG stream matches the
      state seed (determinism invariant).
    - ``tick_rate`` (default ``1.0``): real seconds per tick (1 tick = 1 game
      week per the AGENTS.md time-scale invariant).
    - ``no_autosave`` (default ``False``): wired in T30; the App stores the
      flag today but does not act on it.

    Class attributes:

- ``BINDINGS``: list of ``Binding`` — 10 F-row entries (T24) + 8 single-
  key entries (T25) + 1 extra single-key entry (backtick → toggle_pause,
  Wave 7) = 19 total, in order. Each entry's ``action`` resolves to an
  ``action_<name>`` method on this App, which delegates to
  ``action_handlers.<name>``.
    - ``CSS_PATH``: relative path to ``app.tcss`` (the locked CSS).
    """

    # Locked CSS path (relative to this module). Textual loads it at startup.
    CSS_PATH: ClassVar[str] = _CSS_FILE

    # F1..F10 + 8 single-key + 1 extra (backtick → toggle_pause) bindings,
    # registered at class-body evaluation. The class attribute is locked
    # to byte-equal the registry output (T24/T25/Wave-7 contracts);
    # ``priority=True`` is set at RUNTIME via
    # ``promote_bindings_to_priority`` so the App wins the keypress race
    # against child widgets without breaking the registry equality tests.
    BINDINGS: ClassVar[list[Any]] = [
        *register_f_bindings(),
        *register_single_key_bindings(),
        *register_extra_bindings(),
    ]

    def __init__(
        self,
        seed: int = 42,
        tick_rate: float = 1.0,
        no_autosave: bool = False,
    ) -> None:
        """Initialize state, engine, bus. The tick timer starts in ``on_mount``.

        Given: ``seed``, ``tick_rate``, ``no_autosave``
        When: ``HtopTycoonApp(...)`` is constructed
        Then: ``self.state`` is a populated ``GameState`` from
              ``new_started_game(seed)`` (5 employees, 1 dept, 1 product,
              3 competitors — per Wave 6 plan amendment), ``self.engine``
              is a ``TickEngine(seed)``, ``self.event_bus`` is an
              ``EventBus``, and the three config flags are stored on the
              instance.
        """
        super().__init__()
        self.seed: int = seed
        self.tick_rate: float = tick_rate
        self.no_autosave: bool = no_autosave

        self.state: GameState = new_started_game(seed)
        self.engine: TickEngine = TickEngine(seed)
        self.event_bus: EventBus = EventBus()
        self._rng = self.engine._rng

        self._tick_timer: Timer | None = None
        self._last_action: str | None = None
        self._selected_employee_id: EmployeeId | None = None

        # Sort cycle index for F6 (cycle_sort). Incremented modulo the
        # length of the cycle tuple in action_handlers.
        self._sort_cycle_index: int = 0

        # Set of employee ids tagged by Space (T25: marker only, no bulk
        # action). Per the plan MUST-NOT-DO, Space is purely visual for
        # v0.1.0; bulk fire via tagged employees is deferred.
        self._tagged_employee_ids: set[EmployeeId] = set()

        self._save_path: Path = _default_xdg_save_path()
        self._autosave_every: int = self._load_autosave_every()

        # Transient flag set by F10 (QuitOrSellScreen "자발적 매각" button).
        # Consumed by the next ``_tick_once`` which threads ``player_action="sell"``
        # into ``evaluate_endings`` so the VOLUNTARY_SALE ending can trigger.
        self._pending_sell: bool = False
        # Pause flag toggled by the #pause-button (UI button in the header).
        # When True, ``_tick_once`` returns early so game time, payroll,
        # products, and events are all frozen. Player actions (F7/F8/F9,
        # new game, load) still work — only the per-tick clock is halted.
        # The button is the user-facing affordance (Wave 7 rev 3) because
        # keyboard shortcuts conflicted (F11 = macOS "Show Desktop", F12 =
        # Textual 0.89.1 F-key prefix-match bug, backtick = Pilot/tmux
        # key-name quirk). A visible button sidesteps all of those.
        self._paused: bool = False
        self._delegated: bool = False  # Wave 8: Auto-Manager delegation flag
        self._auto_manager: AutoManager = AutoManager(load_balance())

    # ------------------------------------------------------------------ layout

    def compose(self) -> Any:
        """Compose the locked 5-region layout (header / metrics / body / alerts / footer).

        T31 wires the real T17-T22 widgets into the previously-Static
        placeholders. The locked instance counts (6 types / 8 instances):
            1 GameHeader  + 3 MetricBar (cpu/mem/swap) + 1 OrgTree +
            1 EmployeeTable + 1 Alert + 1 HtopFooter.

        Wave 7 rev 3: an extra #pause-button is yielded next to the
        GameHeader so the user can toggle pause/resume with a mouse
        click. The button replaces the earlier keyboard bindings (F11,
        F12, backtick) which each had a platform- or framework-level
        conflict. The button is the only user-facing affordance for
        the time-stop feature now.
        """
        with Horizontal(id="header-row"):
            yield GameHeader(self.event_bus, id="header")
            yield Button("▶ 일시정지", id="pause-button", variant="primary")
        with Vertical(id="metrics"):
            yield MetricBar("CPU", id="cpu")
            yield MetricBar("MEM", id="mem")
            yield MetricBar("SWAP", id="swap")
        with Horizontal(id="body"):
            yield OrgTree(self.state, id="org-tree")
            employees = list(self.state.employees.values())
            table = EmployeeTable(
                employees=employees,
                departments=self.state.departments,
            )
            # EmployeeTable.__init__ doesn't accept id=; assign after
            # construction (before mount) so the locked CSS rule
            # ``#employee-panel { width: 1fr }`` still applies.
            table.id = "employee-panel"
            # Row-mode cursor: arrow keys move a row cursor; Enter emits
            # RowSelected which the App's ``on_data_table_row_selected``
            # handler turns into ``_selected_employee_id``.
            table.cursor_type = "row"
            yield table
        yield Alert(self.event_bus, id="alerts")
        yield HtopFooter(id="footer")

    # ------------------------------------------------------------------ selection wiring

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """When the user presses Enter on an EmployeeTable row, capture the id.

        Locks the contract from T31: pressing ``down`` + ``enter`` selects
        the first employee. The DataTable already tracks the highlighted
        row via its cursor; this handler copies the highlighted row's
        EmployeeId into ``self._selected_employee_id`` so F7/F8/F9 can
        act on it.
        """
        try:
            emp_id = EmployeeId(str(event.row_key.value))
        except (AttributeError, TypeError):
            return
        if emp_id in self.state.employees:
            self._selected_employee_id = emp_id

    # ------------------------------------------------------------------ lifecycle

    def on_mount(self) -> None:
        """Start the periodic tick via ``set_interval`` using the locked wrapper.

        Also focuses the EmployeeTable so the user can immediately use
        Down/Enter/Space without pressing Tab first. Without this, the
        initial focus lands on OrgTree and F7/F8/F9 silently alert
        "직원을 선택하세요" because no row is ever selected.
        """
        self._tick_timer = self.set_interval(
            self.tick_rate,
            self._tick_once,
            name="htop-tycoon-tick",
        )
        # Promote every registered binding to ``priority=True`` so the App
        # wins the keypress race against child widgets (OrgTree has its own
        # ``t``; DataTable has built-in ``up``/``down``/``space``/``enter``).
        promote_bindings_to_priority(self)
        # Initial paint of header + metric bars from the current state so the
        # first frame is non-empty (header shows tick=0, bars show ok/0%).
        refresh_widgets_from_state(self)
        subscribe_focus_events(self)
        # Auto-focus the EmployeeTable so Down/Enter/Space land on it
        # without the user pressing Tab first. F7/F8/F9 then have a
        # valid cursor target the moment the user starts navigating.
        self._focus_employee_table()
        # Initialize the #pause-button label + CSS class so the first
        # frame already reflects the running state instead of the
        # ``compose``-time static default.
        self._wire_pause_button()

    def _focus_employee_table(self) -> None:
        """Focus the EmployeeTable so cursor keys + Enter land on it.

        Called once from ``on_mount``. Wrapped in try/except because the
        EmployeeTable ID is set in ``compose`` but Textual's focus
        machinery is forgiving about late-mounted widgets.
        """
        try:
            self.query_one("#employee-panel").focus()
        except Exception:
            pass

    def _wire_pause_button(self) -> None:
        """Initialize the #pause-button label + CSS class for ``_paused``.

        Wave 7 rev 3: replaces the earlier keyboard bindings (F11, F12,
        backtick) which all had platform or framework conflicts. The
        button is the only user-facing affordance for the time-stop
        feature; ``Button.Pressed`` message handling (vs. the ``action``
        parameter) is used because Pilot does not reliably trigger the
        latter.
        """
        self._refresh_pause_button_label()
        self._update_header_pause_indicator()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses: route #pause-button to ``action_toggle_pause``.

        Other buttons (in modal screens like SetupScreen, HelpScreen,
        etc.) are handled by their own screen-level handlers, which
        run first in Textual's message routing. This App-level handler
        only fires for buttons whose message bubbles up — in practice
        the #pause-button is the only App-level button.
        """
        if event.button.id == "pause-button":
            self.action_toggle_pause()

    def _refresh_pause_button_label(self) -> None:
        """Sync the #pause-button label and ``is-paused`` CSS class to ``_paused``.

        Three user-visible cues stay in lockstep: the label itself
        (``"▶ 일시정지"`` vs ``"⏸ 재생"``), the button's background color
        (driven by ``.is-paused`` in :file:`app.tcss`), and the
        ``⏸ 일시정지`` prefix on the :class:`GameHeader` top-line.

        Silent no-op when the button is absent (e.g. test setups that
        bypass ``compose``).
        """
        try:
            btn = self.query_one("#pause-button", Button)
        except Exception:
            return
        btn.label = "⏸ 재생" if self._paused else "▶ 일시정지"
        btn.set_class(self._paused, "is-paused")

    def _update_header_pause_indicator(self) -> None:
        """Push the current ``_paused`` flag to the mounted ``GameHeader``.

        Looks up ``#header`` and calls :meth:`GameHeader.set_paused` so
        the ``⏸ 일시정지`` prefix flips in lockstep with the button.
        Silent no-op when the header is absent.
        """
        try:
            header = self.query_one("#header", GameHeader)
        except Exception:
            return
        header.set_paused(self._paused)

    def _update_header_delegate_indicator(self) -> None:
        """Push the current ``_delegated`` flag to the mounted ``#header``.

        Wave 8 (delegation): called from `action_toggle_delegate` (d key
        press) and from `check_action` (auto-disable on any non-toggle
        action). The header is updated in lockstep with the flag so the
        `위임` prefix is visible the moment delegation toggles.

        Silent no-op when the header is not yet mounted (the ``try/except``
        mirrors the pause indicator pattern).
        """
        try:
            header = self.query_one("#header", GameHeader)
        except Exception:
            return
        header.set_delegated(self._delegated)

    def check_action(
        self, action: str, parameters: tuple[object, ...]
    ) -> bool:
        """Pre-action hook: disable delegation on any non-toggle action.

        Wave 8 (delegation): the design spec (docs/superpowers/specs/
        2026-06-29-delegation-design.md) says "manual override disables
        delegation" — pressing any other key (other than `d` again, or
        `p` for pause which is independent) should auto-disable the AI.

        Whitelist: `toggle_delegate` and `toggle_pause` (both keep
        delegation as-is). Everything else flips `_delegated = False`
        and refreshes the header indicator.

        Returns True so Textual proceeds with the action (the spec
        doesn't reject — it just disables delegation on the side).
        """
        if self._delegated and action not in ("toggle_delegate", "toggle_pause"):
            self._delegated = False
            self._update_header_delegate_indicator()
        return True

    def _apply_state_change(self, new_state: GameState) -> None:
        """Replace ``app.state`` and refresh every widget that depends on it.

        Used by action handlers (F7/F8/F9, etc.) that mutate state via
        ``engine_actions``. The per-tick pipeline (``_tick_once``) does
        the same fan-out via ``refresh_widgets_from_state`` + a
        ``StateUpdated`` publish; this helper does BOTH plus the
        EmployeeTable/OrgTree refresh that ``refresh_widgets_from_state``
        doesn't touch. Without it, F7/F8/F9 would update the state but
        leave the table cells, tree, and metric bars stale.
        """
        from htop_tycoon.engine.events import StateUpdated

        self.state = new_state
        # Header subscribes to StateUpdated so it gets the new time /
        # company / department / product labels. Metric bars + alert
        # banner are also driven by this event.
        self.event_bus.publish(StateUpdated(state=new_state))
        refresh_widgets_from_state(self)
        # EmployeeTable and OrgTree hold their own data (constructed
        # once with the starting state) so they need an explicit refresh
        # — they don't subscribe to StateUpdated because sort/filter
        # live on the table itself.
        from htop_tycoon.ui.widgets.employee_table import EmployeeTable
        from htop_tycoon.ui.widgets.org_tree import OrgTree

        for emp_table in self.query(EmployeeTable):
            emp_table.refresh_from_state(
                list(new_state.employees.values()), new_state.departments
            )
        for org_tree in self.query(OrgTree):
            org_tree.refresh_from_state(new_state)

    # ------------------------------------------------------------------ locked wiring

    def _tick_once(self) -> None:
        """Single tick — the locked wiring wrapper (NO-ARG, supplies state).

        Drives the full per-tick pipeline (Wave 6 patch): time → products →
        competitors → events → revenue → payroll → endings. On any ending
        trigger, the tick timer is stopped and the game pauses for review.
        Also threads the transient ``_pending_sell`` flag into the ending
        evaluator (consumed once per tick) so the F10 voluntary-sale
        intent reaches the locked VOLUNTARY_SALE condition.

        Wave 8 (delegation): when ``_delegated`` is True, an AI block runs
        BEFORE the normal pipeline so the AI's decisions (hire/fire/demote
        + regime-aware focus) are applied to the pre-tick state. The AI
        consumes rng from the engine's shared stream in a fixed order so
        determinism is preserved. When ``_delegated`` is False (the default
        for ``new_game(seed=42)``), the AI block is skipped entirely — no
        rng consumption — so test_playthrough.py's frozen hash is
        unaffected.
        """
        # Pause gate (Wave 7 rev 2): when backtick has toggled the clock
        # off, return BEFORE any engine pipeline runs. The ``set_interval``
        # timer keeps firing (Textual owns the lifecycle); we just no-op
        # the callback.
        # All other player actions (F7/F8/F9, 새 게임, etc.) still go
        # through their normal paths.
        if self._paused:
            return
        from htop_tycoon.data import load_balance
        from htop_tycoon.engine.cash_flow import process_payroll, process_revenue
        from htop_tycoon.engine.competitor_ai import step_competitors
        from htop_tycoon.engine.ending import apply_ending, evaluate_endings
        from htop_tycoon.engine.event_chain import evaluate_events, load_events_catalog
        from htop_tycoon.engine.product_market import tick_products

        balance = load_balance()
        events_catalog = load_events_catalog()
        rng = self.engine._rng

        state = self.state
        if self._delegated:
            self._dispatch_auto_manager_tick(state)
            state = self.state

        state = self.engine.advance(state, 1)
        state = tick_products(state, rng)
        state, _comp_events = step_competitors(state, rng)
        state, _fired, _scheduled = evaluate_events(
            state, rng, balance, events_catalog, []
        )
        state = process_revenue(state, balance)
        state = process_payroll(state, balance)
        # Snapshot + clear the pending sell flag so a single F10 press
        # triggers exactly one tick of VOLUNTARY_SALE evaluation. Without
        # the clear, every subsequent tick would also force-sell.
        player_action = "sell" if self._pending_sell else None
        if self._pending_sell:
            self._pending_sell = False
        ending = evaluate_endings(state, balance, player_action=player_action)
        if ending is not None:
            state, _end_events = apply_ending(state, ending)
            if self._tick_timer is not None:
                self._tick_timer.stop()
                self._tick_timer = None

        self.state = state
        self.event_bus.publish(StateUpdated(state=state))
        refresh_widgets_from_state(self)
        self._maybe_autosave()

    def _dispatch_auto_manager_tick(self, state: GameState) -> None:
        """Dispatch one tick of AutoManager + apply_ai_suggested_focus.

        Wave 8 (delegation): when _delegated is True, the AI runs each
        tick to emit decisions (hire/fire/demote/...) and to apply
        regime-aware focus changes (T44's regime_aware_focus_suggestion).

        The AI consumes one or more rng.float() calls per tick, so
        determinism is preserved per GameRNG semantics.

        PURE wrapper: no in-place state mutation; produces a new
        GameState (or returns same state when no-op). The caller
        (the existing tick pipeline) takes the returned state via
        dataclasses.replace.
        """
        from htop_tycoon.engine.ai_focus_policy import apply_ai_suggested_focus

        decisions = self._auto_manager.decide(state, self._rng)
        new_state = state
        for decision in decisions:
            new_state, _ = self._apply_ai_decision(new_state, decision)

        balance = load_balance()
        new_state, focus_signals = apply_ai_suggested_focus(
            new_state, balance, new_state.tick
        )
        for sig in focus_signals:
            self.event_bus.publish(sig)

        self.state = new_state

    def _apply_ai_decision(
        self, state: GameState, decision: Decision
    ) -> tuple[GameState, list[Event]]:
        """Apply one AutoManager decision to the state.

        Maps:
          - ``hire`` → engine_actions.hire(state, dept_id, self._rng)
          - ``fire`` → engine_actions.fire(state, target)
          - ``demote`` → engine_actions.demote(state, target)
          - ``promote`` → engine_actions.promote(state, target)
          - ``counter_cut`` / ``marketing_blitz`` → defensive noop with
            AlertRaised("AI: 공격 액션 미구현 (TODO Wave 9+)", "warn")

        Returns (new_state, events). The existing pipeline will publish
        events through the bus after the AI block.
        """
        from htop_tycoon.engine import actions as engine_actions
        from htop_tycoon.engine.events import AlertRaised, Event

        action = decision.action
        target = decision.target
        events: list[Event] = []

        if action == "hire":
            new_state, evs = engine_actions.hire(state, target, self._rng)
            return new_state, list(evs)
        if action == "fire":
            new_state, evs = engine_actions.fire(state, target)
            return new_state, list(evs)
        if action == "demote":
            new_state, evs = engine_actions.demote(state, target)
            return new_state, list(evs)
        if action == "promote":
            new_state, evs = engine_actions.promote(state, target)
            return new_state, list(evs)
        if action in ("counter_cut", "marketing_blitz"):
            return state, [
                AlertRaised(
                    message_ko="AI: 공격 액션 미구현 (TODO Wave 9+)",
                    severity="warn",
                )
            ]
        return state, events

    def _maybe_autosave(self) -> None:
        """Silently save ``state`` to ``_save_path`` every N ticks.

        Fires when ``state.tick`` is a positive multiple of
        ``balance["save"]["autosave_every_n_ticks"]`` AND autosave is
        enabled (i.e. ``no_autosave`` is False). Errors are logged but
        do NOT propagate — autosave is a background convenience, not a
        critical path; the user can always press F2 → Save manually.

        Per plan MUST-NOT-DO: no UI feedback on success (silent save).
        Errors are logged so a CI failure surfaces via stderr.
        """
        if self.no_autosave:
            return
        if self._autosave_every <= 0:
            return
        if self.state.tick <= 0:
            return
        if self.state.tick % self._autosave_every != 0:
            return
        try:
            persistence_save(self.state, self._save_path)
        except OSError:
            _logger.exception(
                "autosave failed: path=%s tick=%d", self._save_path, self.state.tick
            )

    def _load_autosave_every(self) -> int:
        """Return the autosave cadence from ``balance.yaml``.

        Cached once per App instance (balance.yaml is lru-cached by
        ``data.load_balance``). Returns 0 if the key is missing or
        non-positive — 0 disables autosave without raising.
        """
        try:
            value = int(load_balance()["save"]["autosave_every_n_ticks"])
        except (KeyError, TypeError, ValueError):
            return 0
        return max(value, 0)

    # ------------------------------------------------------------------ stub helpers

    def _employee_table(self) -> Any:
        """Return the mounted EmployeeTable widget, or ``None`` when absent.

        Centralizes the ``query_one`` lookup so action callbacks (F3/F4/u
        + space) don't each duplicate the try/except boilerplate. Returns
        ``None`` rather than raising because the lookup happens in a
        Textual keypress callback path where a missing widget should
        silently no-op (consistent with the other helpers' defensive
        style).
        """
        try:
            return self.query_one("#employee-panel")
        except Exception:
            return None

    def _open_dept_picker(self) -> None:
        """Open the department picker overlay (delegated to ``action_filter_by_dept``).

        Kept as a no-op shim for T25 backwards compatibility — the real
        picker UI now lives in :class:`DeptPickerScreen`, pushed by
        ``action_filter_by_dept``. Direct calls to this method (from
        older bindings or tests) become a no-op rather than raising.
        """
        return None

    # ------------------------------------------------------------------ action_* delegations

    # Each ``action_<name>`` below is a thin delegate to the matching
    # function in ``action_handlers``. The bindings list points at these
    # method names; the handler does the real work. The delegations are
    # defined as class-level methods (not lambdas / partials) so
    # Textual's binding dispatcher finds them via standard attribute
    # lookup, and so mypy / IDEs see them as proper methods.

    # F-row (T24)
    def action_show_help(self) -> None:
        """F1 — record the action then push the HelpScreen modal."""
        action_handlers.show_help(self)
        from htop_tycoon.ui.screens.help import HelpScreen as _HS
        self.push_screen(_HS())

    def action_show_setup(self) -> None:
        """F2 — push the SetupScreen modal (save / load / new game / reset).

        T29: ``action_handlers.show_setup`` previously recorded the
        action name and notified the user. It now ALSO pushes the
        SetupScreen so the user can interact with save/load/reset. The
        ``_record`` call is preserved so the T24 contract (every F-key
        sets ``_last_action``) stays green.
        """
        action_handlers.show_setup(self)
        from htop_tycoon.ui.screens.setup import SetupScreen as _SS
        self.push_screen(_SS(self))

    def action_search(self) -> None:
        """F3 — record then push SearchScreen; apply its result on dismiss.

        The SearchScreen dismisses with the typed query (or ``None``).
        On non-None we call ``EmployeeTable.filter_by_name``; on None
        we keep any existing name filter (the user cancelled). A new
        query overrides any prior one (search is the authoritative
        filter for F3 within a session).
        """
        action_handlers.search(self)
        from htop_tycoon.ui.screens.search import SearchScreen as _SC

        def _on_dismiss(result: str | None) -> None:
            if result is None:
                return
            table = self._employee_table()
            if table is not None and hasattr(table, "filter_by_name"):
                table.filter_by_name(result)

        self.push_screen(_SC(), callback=_on_dismiss)

    def action_filter(self) -> None:
        """F4 — record then push FilterScreen; apply its result on dismiss.

        The FilterScreen dismisses with ``(min, max)`` or ``None``.
        On ``(min, max)`` we call ``EmployeeTable.filter_by_skill_range``;
        on ``None`` we keep the current range (cancelled).
        """
        action_handlers.filter(self)
        from htop_tycoon.ui.screens.filter import FilterScreen as _FC

        def _on_dismiss(result: tuple[int | None, int | None] | None) -> None:
            if result is None:
                return
            table = self._employee_table()
            if table is not None and hasattr(table, "filter_by_skill_range"):
                table.filter_by_skill_range(result)

        self.push_screen(_FC(), callback=_on_dismiss)

    def action_toggle_tree(self) -> None:
        """F5 / single-key ``t`` — see ``action_handlers.toggle_tree``."""
        action_handlers.toggle_tree(self)

    def action_cycle_sort(self) -> None:
        """F6 — see ``action_handlers.cycle_sort``."""
        action_handlers.cycle_sort(self)

    def action_promote_selected(self) -> None:
        """F7 — see ``action_handlers.promote_selected``."""
        action_handlers.promote_selected(self)

    def action_demote_selected(self) -> None:
        """F8 — see ``action_handlers.demote_selected``."""
        action_handlers.demote_selected(self)

    def action_fire_selected(self) -> None:
        """F9 — see ``action_handlers.fire_selected``."""
        action_handlers.fire_selected(self)

    def action_quit_or_sell(self) -> None:
        """F10 — record then push QuitOrSellScreen; act on its result.

        The QuitOrSellScreen dismisses with ``"quit"``, ``"sell"``, or
        ``None``. ``"quit"`` calls ``self.exit()`` (Textual's standard
        App shutdown); ``"sell"`` flags ``_pending_sell = True`` so the
        next tick triggers the ``VOLUNTARY_SALE`` ending (per T15 contract:
        ``ctx.player_action == "sell"``); ``None`` is a no-op cancel.
        """
        action_handlers.quit_or_sell(self)

    def action_toggle_pause(self) -> None:
        """Toggle the per-tick clock (일시정지 / 재생).

        Wave 7 rev 3: invoked by the ``#pause-button`` click handler (the
        only user-facing affordance for the time-stop feature after the
        F11/F12/backtick keyboard bindings all proved problematic).
        Delegates to :func:`action_handlers.toggle_pause` which flips
        ``self._paused``. ``_tick_once`` reads the flag and returns early
        when paused, freezing game time, payroll, and product evolution.
        Player actions (F7/F8/F9, 새 게임, etc.) still go through their
        normal paths — only the automatic clock is halted, matching the
        htop-style "pause" affordance.

        We also call :meth:`_refresh_pause_button_label` so the button
        label flips between ``"▶ 일시정지"`` (game running) and
        ``"⏸ 재생"`` (game paused) on every click, and we propagate the
        paused flag to the :class:`GameHeader` so the top-line indicator
        (``⏸ 일시정지`` prefix) updates in lockstep with the button.

        Must NOT push :class:`QuitOrSellScreen`: that was a copy-paste
        regression from an earlier draft where pause shared the F10
        binding. The pause feature has nothing to do with quit/sell and
        pushing the modal here would cover the button the user just
        clicked, hiding the very state change they triggered.
        """
        action_handlers.toggle_pause(self)
        self._refresh_pause_button_label()
        self._update_header_pause_indicator()

    def action_toggle_delegate(self) -> None:
        """Toggle the Auto-Manager (위임) delegation flag.

        Bound to `d` via register_extra_bindings. The flag is on the
        App (not on GameState — the engine state is frozen). The
        dispatch is handled in _tick_once; the header indicator
        refreshes immediately.
        """
        from htop_tycoon.ui.action_handlers import toggle_delegate
        toggle_delegate(self)

    # Single-key (T25)
    def action_filter_by_dept(self) -> None:
        """Single-key ``u`` — record then push DeptPickerScreen; apply result.

        The DeptPickerScreen dismisses with the picked ``DepartmentId``
        string, the sentinel ``"__all__`` (clear filter), or ``None``
        (cancelled). We translate ``"__all__`` back to ``None`` and call
        ``EmployeeTable.filter_by_department``.
        """
        action_handlers.filter_by_dept(self)
        from htop_tycoon.ui.screens.dept_picker import DeptPickerScreen as _DP

        def _on_dismiss(result: str | None) -> None:
            if result is None:
                return  # cancelled
            from htop_tycoon.domain.state import DepartmentId as _DID

            dept_id = None if result == "__all__" else _DID(result)
            table = self._employee_table()
            if table is not None and hasattr(table, "filter_by_department"):
                table.filter_by_department(dept_id)

        self.push_screen(_DP(self), callback=_on_dismiss)

    def action_sort_by_satisfaction(self) -> None:
        """Single-key ``m`` — see ``action_handlers.sort_by_satisfaction``."""
        action_handlers.sort_by_satisfaction(self)

    def action_sort_by_salary(self) -> None:
        """Single-key ``p`` — see ``action_handlers.sort_by_salary``."""
        action_handlers.sort_by_salary(self)

    def action_sort_by_time(self) -> None:
        """Single-key ``T`` — see ``action_handlers.sort_by_time``."""
        action_handlers.sort_by_time(self)

    def action_sort_by_skill(self) -> None:
        """Internal sort (no keybinding) — see ``action_handlers.sort_by_skill``."""
        action_handlers.sort_by_skill(self)

    def action_cursor_up(self) -> None:
        """Single-key ``up`` — see ``action_handlers.cursor_up``."""
        action_handlers.cursor_up(self)

    def action_cursor_down(self) -> None:
        """Single-key ``down`` — see ``action_handlers.cursor_down``."""
        action_handlers.cursor_down(self)

    def action_tag_selected(self) -> None:
        """Single-key ``space`` — see ``action_handlers.tag_selected``."""
        action_handlers.tag_selected(self)


# ------------------------------------------------------------------
# Path note: the CSS file is referenced as a relative string
# (``CSS_PATH = "app.tcss"``). Textual resolves this relative to the
# module file (i.e. ``src/htop_tycoon/ui/app.tcss``). Keeping it as a
# string (not a Path) matches Textual's documented convention and
# works both in production (``python -m htop_tycoon``) and in Pilot
# tests (Textual locates the file relative to the module).
# ------------------------------------------------------------------
