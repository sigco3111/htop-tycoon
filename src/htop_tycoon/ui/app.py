"""htop_tycoon.ui.app — HtopTycoonApp: Textual App skeleton + locked 5-region layout.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 434-456 (T16):

- ``HtopTycoonApp`` subclasses ``textual.app.App`` and accepts
  ``seed: int = 42``, ``tick_rate: float = 1.0``, ``no_autosave: bool = False``.
- ``BINDINGS = []`` is a class attribute (filled in T24-T25).
- CSS lives in ``app.tcss`` (sibling of this module) and defines the locked
  5-region layout: header / metrics / body (org-tree + employee-panel) /
  alerts / footer.
- ``on_mount`` starts the periodic tick via ``self.set_interval`` using the
  locked wrapper ``self._tick_once`` — see the wiring note in
  ``_tick_once``'s docstring (do NOT call ``engine.advance`` directly).
- ``_tick_once`` is the CRITICAL wiring: a no-arg wrapper that supplies the
  current ``self.state`` to ``engine.advance``. Textual's ``set_interval``
  passes no arguments, but ``engine.advance(state, n_ticks)`` requires the
  state, so the wrapper is the only correct pattern.

This module is the UI entry point. UI handlers MUST NOT mutate ``self.state``
directly — the engine is the only writer (per AGENTS.md "State boundary"
invariant). The wrapper here delegates to ``engine.advance`` and rebinds
``self.state`` to the returned new state, then publishes events via the bus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import App
from textual.containers import Horizontal
from textual.widgets import Static

from htop_tycoon.domain.state import GameState, new_game
from htop_tycoon.engine.events import EventBus
from htop_tycoon.engine.tick import TickEngine

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

    - ``BINDINGS``: list of ``Binding`` — empty until T24-T25.
    - ``CSS_PATH``: relative path to ``app.tcss`` (the locked CSS).
    """

    # Locked CSS path (relative to this module). Textual loads it at startup.
    CSS_PATH: ClassVar[str] = _CSS_FILE

    # Key bindings — filled in T24-T25. Empty today means "no keybinds yet".
    BINDINGS: ClassVar[list[Any]] = []

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

        ``self.state``, ``self.engine``, ``self.event_bus`` are initialized
        eagerly (in ``__init__``, not in ``on_mount``) so plain-Python
        smoke tests that construct the App without Pilot can still inspect
        them. The interval timer itself starts in ``on_mount`` because
        Textual's timer machinery requires a running event loop.
        """
        super().__init__()
        # Stash config on the instance so tests + T30's CLI can read them.
        self.seed: int = seed
        self.tick_rate: float = tick_rate
        self.no_autosave: bool = no_autosave

        # State + engine + bus. The engine is seeded with the SAME seed as
        # new_game so the determinism invariant (per AGENTS.md) holds.
        self.state: GameState = new_game(seed)
        self.engine: TickEngine = TickEngine(seed)
        self.event_bus: EventBus = EventBus()

        # ``_tick_timer`` is populated in ``on_mount`` (Textual's
        # ``set_interval`` returns a Timer instance). Exposed as an
        # attribute so tests can assert the timer exists + has the right
        # interval.
        self._tick_timer: Timer | None = None

    # ------------------------------------------------------------------ layout

    def compose(self) -> Any:
        """Compose the locked 5-region layout (header / metrics / body / alerts / footer).

        Each region is a ``Static`` placeholder for T16. T17-T22 will replace
        them with real widgets (MetricBar, OrgTree, EmployeePanel, Alerts,
        HeaderCounter, FooterHints). The IDs MUST match the locked CSS in
        ``app.tcss``.
        """
        # Header (h=1) — T21 HeaderCounter replaces this with a tick counter.
        yield Static(id="header")
        # Metrics row (h=5) — T17 MetricBar x 3 (CPU/MEM/SWAP) replaces this.
        yield Static(id="metrics")
        # Body: horizontal split with org-tree (30%) + employee-panel (1fr).
        with Horizontal(id="body"):
            yield Static(id="org-tree")
            yield Static(id="employee-panel")
        # Alerts (h=3, dock bottom) — T20 Alerts widget replaces this.
        yield Static(id="alerts")
        # Footer (h=1, dock bottom) — T22 FooterHints replaces this.
        yield Static(id="footer")

    # ------------------------------------------------------------------ lifecycle

    def on_mount(self) -> None:
        """Start the periodic tick via ``set_interval`` using the locked wrapper.

        Given: a mounted HtopTycoonApp
        When: ``on_mount`` fires (after ``compose``)
        Then: ``self._tick_timer`` is a ``Timer`` whose interval is
              ``self.tick_rate`` and whose callback is ``self._tick_once``.

        Note: ``set_interval`` accepts the wrapper method as a bound method
        (Textual will call it with no arguments). The wrapper internally
        supplies ``self.state`` to ``engine.advance``.
        """
        self._tick_timer = self.set_interval(
            self.tick_rate,
            self._tick_once,
            name="htop-tycoon-tick",
        )

    # ------------------------------------------------------------------ locked wiring

    def _tick_once(self) -> None:
        """Single tick — the locked wiring wrapper (NO-ARG, supplies state).

        This is the ONLY correct way to drive ``TickEngine.advance`` from
        Textual's ``set_interval``. Direct ``self.set_interval(
        self.engine.advance, ...)`` is forbidden because:

            1. ``engine.advance(state, n_ticks=1)`` requires the current
               ``GameState`` as its first positional argument.
            2. ``set_interval`` invokes its callback with NO arguments.

        Calling ``engine.advance`` directly would raise ``TypeError`` at the
        first tick. Wrapping in ``_tick_once`` is the only correct pattern.

        Side-effects:
            - ``self.state`` is REBOUND to a new ``GameState`` (the engine
              returns a fresh state via ``dataclasses.replace`` — the input
              is untouched, per the immutability invariant).
            - ``self.event_bus.publish_many(events)`` dispatches the engine
              output events to subscribers.

        Future note: when T9 evolves to return ``(GameState, list[Event])``
        (the AGENTS.md invariant: "pure functions return (GameState, list[Event])"),
        this wrapper naturally consumes the tuple form — today's code uses
        the current single-return shape and publishes an empty event list.
        """
        # Engine.advance is deterministic for a given (state, n_ticks) pair
        # because the engine advances its own RNG once per tick. The output
        # state is fresh; ``self.state`` is REBOUND, never mutated.
        new_state = self.engine.advance(self.state, 1)
        self.state = new_state
        # No engine events today; ``publish_many([])`` is a safe no-op per
        # the EventBus contract. When T9 evolves to return (state, events),
        # swap this for ``self.engine.advance(self.state, 1)[1]`` and
        # unpack both values.
        self.event_bus.publish_many([])


# ------------------------------------------------------------------
# Path note: the CSS file is referenced as a relative string
# (``CSS_PATH = "app.tcss"``). Textual resolves this relative to the
# module file (i.e. ``src/htop_tycoon/ui/app.tcss``). Keeping it as a
# string (not a Path) matches Textual's documented convention and
# works both in production (``python -m htop_tycoon``) and in Pilot
# tests (Textual locates the file relative to the module).
# ------------------------------------------------------------------
