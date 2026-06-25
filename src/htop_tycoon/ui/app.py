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
  ``bindings.registry.register_single_key_bindings()``. Total length: 18.

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
from textual.widgets import DataTable

from htop_tycoon.bindings.registry import (
    register_f_bindings,
    register_single_key_bindings,
)
from htop_tycoon.data import load_balance
from htop_tycoon.domain.state import EmployeeId, GameState, new_game
from htop_tycoon.engine.events import EventBus, StateUpdated
from htop_tycoon.engine.tick import TickEngine
from htop_tycoon.persistence.serialize import save as persistence_save
from htop_tycoon.ui import action_handlers
from htop_tycoon.ui.app_wiring import (
    promote_bindings_to_priority,
    refresh_widgets_from_state,
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
      key entries (T25) = 18 total, in order. Each entry's ``action``
      resolves to an ``action_<name>`` method on this App, which delegates
      to ``action_handlers.<name>``.
    - ``CSS_PATH``: relative path to ``app.tcss`` (the locked CSS).
    """

    # Locked CSS path (relative to this module). Textual loads it at startup.
    CSS_PATH: ClassVar[str] = _CSS_FILE

    # F1..F10 + single-key bindings — registered at class-body evaluation.
    # Both ``register_*`` functions return fresh lists; concatenation is
    # safe and produces an independent list per class load. The class
    # attribute is locked to byte-equal the registry output (T24/T25
    # contract); the App-level ``priority=True`` is set at RUNTIME via
    # ``self._promote_bindings_to_priority()`` so the App wins the
    # keypress race against child widgets without breaking the registry
    # equality assertions in ``test_bindings_pilot.py``.
    BINDINGS: ClassVar[list[Any]] = [
        *register_f_bindings(),
        *register_single_key_bindings(),
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
        Then: ``self.state`` is a ``GameState`` from ``new_game(seed)``,
              ``self.engine`` is a ``TickEngine(seed)``,
              ``self.event_bus`` is an ``EventBus``,
              and the three config flags are stored on the instance.
        """
        super().__init__()
        self.seed: int = seed
        self.tick_rate: float = tick_rate
        self.no_autosave: bool = no_autosave

        self.state: GameState = new_game(seed)
        self.engine: TickEngine = TickEngine(seed)
        self.event_bus: EventBus = EventBus()

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

    # ------------------------------------------------------------------ layout

    def compose(self) -> Any:
        """Compose the locked 5-region layout (header / metrics / body / alerts / footer).

        T31 wires the real T17-T22 widgets into the previously-Static
        placeholders. The locked instance counts (6 types / 8 instances):
            1 GameHeader  + 3 MetricBar (cpu/mem/swap) + 1 OrgTree +
            1 EmployeeTable + 1 Alert + 1 HtopFooter.
        """
        yield GameHeader(self.event_bus, id="header")
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
        """Start the periodic tick via ``set_interval`` using the locked wrapper."""
        self._tick_timer = self.set_interval(
            self.tick_rate,
            self._tick_once,
            name="htop-tycoon-tick",
        )
        # Promote every registered binding to ``priority=True`` so the App
        # wins the keypress race against child widgets (OrgTree has its own
        # ``t``; DataTable has built-in ``up``/``down``/``space``/``enter``).
        # Done at runtime — not by rewriting BINDINGS — to preserve the
        # T24/T25 byte-equal registry contract.
        promote_bindings_to_priority(self)
        # Initial paint of header + metric bars from the current state so the
        # first frame is non-empty (header shows tick=0, bars show ok/0%).
        refresh_widgets_from_state(self)

    # ------------------------------------------------------------------ locked wiring

    def _tick_once(self) -> None:
        """Single tick — the locked wiring wrapper (NO-ARG, supplies state).

        Drives the full per-tick pipeline (Wave 6 patch): time → products →
        competitors → events → revenue → payroll → endings. On any ending
        trigger, the tick timer is stopped and the game pauses for review.
        """
        from htop_tycoon.data import load_balance
        from htop_tycoon.engine.cash_flow import process_payroll, process_revenue
        from htop_tycoon.engine.competitor_ai import step_competitors
        from htop_tycoon.engine.ending import apply_ending, evaluate_endings
        from htop_tycoon.engine.event_chain import evaluate_events, load_events_catalog
        from htop_tycoon.engine.product_market import tick_products

        balance = load_balance()
        events_catalog = load_events_catalog()
        rng = self.engine._rng

        state = self.engine.advance(self.state, 1)
        state = tick_products(state, rng)
        state, _comp_events = step_competitors(state, rng)
        state, _fired, _scheduled = evaluate_events(
            state, rng, balance, events_catalog, []
        )
        state = process_revenue(state, balance)
        state = process_payroll(state, balance)
        ending = evaluate_endings(state, balance)
        if ending is not None:
            state, _end_events = apply_ending(state, ending)
            if self._tick_timer is not None:
                self._tick_timer.stop()
                self._tick_timer = None

        self.state = state
        self.event_bus.publish(StateUpdated(state=state))
        refresh_widgets_from_state(self)
        self._maybe_autosave()

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

    def _open_dept_picker(self) -> None:
        """Open the department picker overlay (stub for T25).

        The plan defers the real picker UI to a later todo; for T25 the
        single-key ``u`` binding routes through this method so the
        contract is locked. The body is intentionally empty.
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
        """F1 — see ``action_handlers.show_help``."""
        action_handlers.show_help(self)

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
        """F3 — see ``action_handlers.search``."""
        action_handlers.search(self)

    def action_filter(self) -> None:
        """F4 — see ``action_handlers.filter``."""
        action_handlers.filter(self)

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
        """F10 — see ``action_handlers.quit_or_sell``."""
        action_handlers.quit_or_sell(self)

    # Single-key (T25)
    def action_filter_by_dept(self) -> None:
        """Single-key ``u`` — see ``action_handlers.filter_by_dept``."""
        action_handlers.filter_by_dept(self)

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
