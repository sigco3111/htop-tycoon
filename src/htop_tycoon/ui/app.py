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

from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import App
from textual.containers import Horizontal
from textual.widgets import Static

from htop_tycoon.bindings.registry import (
    register_f_bindings,
    register_single_key_bindings,
)
from htop_tycoon.domain.state import EmployeeId, GameState, new_game
from htop_tycoon.engine.events import EventBus
from htop_tycoon.engine.tick import TickEngine
from htop_tycoon.ui import action_handlers

if TYPE_CHECKING:
    from textual.timer import Timer


# The CSS file lives next to this module; Textual's default ``CSS_PATH``
# resolution expects a string (or Path) relative to the module.
_CSS_FILE = "app.tcss"

__all__ = ["HtopTycoonApp"]


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
    # safe and produces an independent list per class load.
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

    # ------------------------------------------------------------------ layout

    def compose(self) -> Any:
        """Compose the locked 5-region layout (header / metrics / body / alerts / footer).

        Each region is a ``Static`` placeholder for T16. T17-T22 will replace
        them with real widgets (MetricBar, OrgTree, EmployeePanel, Alerts,
        HeaderCounter, FooterHints). The IDs MUST match the locked CSS in
        ``app.tcss``.
        """
        yield Static(id="header")
        yield Static(id="metrics")
        with Horizontal(id="body"):
            yield Static(id="org-tree")
            yield Static(id="employee-panel")
        yield Static(id="alerts")
        yield Static(id="footer")

    # ------------------------------------------------------------------ lifecycle

    def on_mount(self) -> None:
        """Start the periodic tick via ``set_interval`` using the locked wrapper."""
        self._tick_timer = self.set_interval(
            self.tick_rate,
            self._tick_once,
            name="htop-tycoon-tick",
        )

    # ------------------------------------------------------------------ locked wiring

    def _tick_once(self) -> None:
        """Single tick — the locked wiring wrapper (NO-ARG, supplies state)."""
        new_state = self.engine.advance(self.state, 1)
        self.state = new_state
        self.event_bus.publish_many([])

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
        """F2 — see ``action_handlers.show_setup``."""
        action_handlers.show_setup(self)

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
