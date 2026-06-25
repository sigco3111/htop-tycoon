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
from htop_tycoon.engine.metrics import compute_metrics
from htop_tycoon.ui.widgets.metric_bar import MetricBar

if TYPE_CHECKING:
    from htop_tycoon.ui.app import HtopTycoonApp


__all__ = ["promote_bindings_to_priority", "refresh_widgets_from_state"]


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
