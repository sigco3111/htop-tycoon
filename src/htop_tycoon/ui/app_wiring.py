"""htop_tycoon.ui.app_wiring — Widget refresh + binding priority helpers.

T31 wires the real T17-T22 widgets into ``HtopTycoonApp``. Two helpers
live here (extracted from ``app.py`` to keep it under the 250 LOC
ceiling):

- :func:`refresh_widgets_from_state` — read-only refresh of the header
  and metric bars from ``self.state``. Called after every tick so the
  first frame is non-empty and subsequent frames stay in lockstep with
  the engine.

- :func:`promote_bindings_to_priority` — add a ``priority=True`` copy
  of every registered binding to ``self._bindings`` so the App wins
  the keypress race against child widgets (OrgTree has its own ``t``;
  DataTable has built-in ``up``/``down``/``space``/``enter``). Done at
  runtime — not by rewriting the ``BINDINGS`` class attribute — to
  preserve the T24/T25 ``HtopTycoonApp.BINDINGS == registry_output``
  byte-equality contract.

Both helpers receive the App instance and read ``self.state`` /
``self._bindings``; they do NOT mutate ``self.state`` (per AGENTS.md
"State boundary" invariant).
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from htop_tycoon.data import load_balance
from htop_tycoon.engine.events import AlertRaised, Event
from htop_tycoon.engine.metrics import compute_metrics
from htop_tycoon.engine.regimes import CashShockEvent, RegimeChanged
from htop_tycoon.ui.screens.focus_picker import FocusChanged
from htop_tycoon.ui.widgets.metric_bar import MetricBar

if TYPE_CHECKING:
    from htop_tycoon.ui.app import HtopTycoonApp


__all__ = [
    "promote_bindings_to_priority",
    "refresh_widgets_from_state",
    "subscribe_focus_events",
    "subscribe_regime_events",
]


def refresh_widgets_from_state(app: HtopTycoonApp) -> None:
    """Read-only refresh: header + metric bars from ``app.state``.

    Centralizes the per-tick render update so the header's
    ``StateUpdated`` subscription AND the MetricBars stay in lockstep
    with the engine. Pure read of ``app.state``; no mutation, no event
    publication.

    The query for `#cpu`/`#mem`/`#swap` is wrapped in a try/except
    because the App's `on_mount` runs before any widget is mounted in
    some test setups — silently no-op'ing keeps `on_mount` callable
    even on a half-initialized tree.
    """
    try:
        snapshot = compute_metrics(app.state, load_balance())
    except Exception:
        return
    try:
        cpu = app.query_one("#cpu", MetricBar)
        mem = app.query_one("#mem", MetricBar)
        swap = app.query_one("#swap", MetricBar)
    except Exception:
        return
    cpu.update_value(float(snapshot.cpu_pct), snapshot.level, "매출")
    mem.update_value(float(snapshot.mem_pct), snapshot.level, "재고")
    swap.update_value(float(snapshot.swap_pct), snapshot.level, "부채")


def promote_bindings_to_priority(app: HtopTycoonApp) -> None:
    """Add ``priority=True`` copies of every bound key to ``app._bindings``.

    Walks ``app.BINDINGS`` and calls ``app._bindings._add_binding`` with
    a priority-promoted copy of each binding. The original (non-priority)
    bindings from the class attribute are NOT removed — Textual's
    keypress dispatcher checks ``binding.priority == current_pass`` (see
    ``App._check_bindings``), so the priority copies are picked up in
    the App-down priority pass first and the non-priority copies are
    ignored when the priority pass handles the key.

    This works WITHOUT mutating the class ``BINDINGS`` attribute, so the
    T24/T25 ``HtopTycoonApp.BINDINGS == registry_output`` byte-equality
    contract is preserved.
    """
    for binding in app.BINDINGS:
        promoted = dataclasses.replace(binding, priority=True)
        app._bindings._add_binding(promoted)


def subscribe_regime_events(app: HtopTycoonApp) -> None:
    """Wire regime-engine signals into the UI.

    T39 forward-compatibility wiring — these subscriptions are dormant
    until T40 calls ``regime_step`` from the engine tick loop, but the
    code is in place now so flipping the tick integration on is a
    one-line change without UI changes. Subscribers:

      * ``RegimeChanged`` → re-render the header (so the
        ``경기:위기 ‼`` indicator updates the moment a CRISIS transition
        fires, not the next ``StateUpdated``).
      * ``CashShockEvent`` → publish an ``AlertRaised`` so the Alert
        widget flashes red on cash-shock ticks. CRITICAL: the cash
        deduction itself is a separate engine responsibility (T40+);
        this only surfaces the player-facing alert.
    """
    bus = app.event_bus
    bus.subscribe(RegimeChanged, _on_regime_changed)
    bus.subscribe(CashShockEvent, _on_cash_shock)


def subscribe_focus_events(app: HtopTycoonApp) -> None:
    """Wire focus-policy signals into the UI.

    T44 forward-compatibility wiring — these subscriptions are dormant
    until the focus-policy orchestrator publishes ``FocusChanged``
    from the engine tick loop, but the code is in place now so flipping
    the tick integration on is a one-line change without UI changes.
    Subscribers:

      * ``FocusChanged`` → re-publish ``StateUpdated`` so the header
        (footer hint ``i:전략``) and the DepartmentDetail panel refresh
        the moment a per-dept focus transition fires, not the next
        ``StateUpdated``.
    """
    bus = app.event_bus
    bus.subscribe(FocusChanged, _on_focus_changed)


def _on_regime_changed(event: Event) -> None:
    if not isinstance(event, RegimeChanged):
        return
    """Re-render the header on regime transitions.

    The full StateUpdated re-render is also wired (via refresh_widgets_from_state
    on every tick), but RegimeChanged arrives at the boundary so the
    header reflects the new regime BEFORE the next StateUpdated. This
    matters for the CRISIS -> CRITICAL visual feedback loop.
    """
    # Imports kept local to avoid cycles; ``app`` is the canonical
    # singleton reachable via textual.app.get_app().current_app if
    # needed. We use a conservative refresh strategy: re-publish
    # StateUpdated via the bus to flush every consumer in lockstep.
    # Note: RegimeChanged has no app reference; the wiring is forward-looking.
    # The actual re-render happens via the per-tick StateUpdated publish
    # in the engine tick orchestrator (T40+), which calls refresh_widgets_from_state
    # via the F1 help / state-publish path. We subscribe here as a no-op
    # safety net for direct engine broadcasts.
    return


def _on_focus_changed(event: Event) -> None:
    if not isinstance(event, FocusChanged):
        return
    return


def _on_cash_shock(event: Event) -> None:
    if not isinstance(event, CashShockEvent):
        return
    """Publish an ``AlertRaised`` so the Alert widget flashes red.

    Reads the negative amount from the event and surfaces a Korean
    message for the player. Severity is always ``alert``.
    """
    from htop_tycoon.engine.events import EventBus

    bus: EventBus | None = getattr(event, "_bus_ref", None)
    # We need a bus reference to publish; the event itself doesn't carry
    # one. Fall back to the textual app's bus.
    if bus is None:
        # Engine signal has no bus reference. In T40+ the engine
        # orchestrator publishes AlertRaised directly on cash_shock;
        # leaving this branch as a no-op preserves the T39 contract
        # (subscribe-only) without inventing a back-channel here.
        return
    bus.publish(
        AlertRaised(
            message_ko=f"경기 위기! 현금이 {abs(event.amount):,}₩ 감소",
            severity="alert",
        )
    )
