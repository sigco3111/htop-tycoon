"""htop_tycoon.ui.widgets.metric_bar - htop-style horizontal metric bar widget.

Locks the contract from .omo/plans/htop-tycoon.md line 458-467 (T17):

- ``MetricBar`` subclasses ``textual.widgets.Static`` and renders a
  horizontal bar (Unicode full-block ``\\u2588`` filled, light-shade
  ``\\u2591`` empty) of width 30.
- Color comes from the severity level:
    - ``ok``    -> green ``#00ff00``
    - ``warn``  -> yellow ``#ffff00``
    - ``alert`` -> red ``#ff0000``
- Label format: ``NAME[label_ko]  BAR  XX%  level`` (two spaces between
  sections; brackets are literal characters, not Rich markup tags).
- Three instances stack vertically (CPU / MEM / SWAP) inside the locked
  ``#metrics`` region of the App layout.
- ``update_value(pct, level, label_ko) -> None`` is the only mutator
  exposed to callers. The widget reads its data via the explicit
  arguments (it does NOT subscribe to the engine or the EventBus; the
  App wires the call after each tick).
"""

from __future__ import annotations

from typing import Any, Literal

from rich.text import Text
from textual.widgets import Static

__all__ = ["BAR_WIDTH", "LEVEL_COLORS", "MetricBar"]

# Locked bar width: 30 chars (htop-like; not too wide for the 5-region
# layout). Exposed as a module constant so the Pilot test can assert
# the locked value.
BAR_WIDTH: int = 30

# Locked fg color per severity level. The hex codes match htop's
# canonical palette (ok=green, warn=yellow, alert=red) and are
# intentionally NOT sourced from ``balance.yaml`` (UI palette is a
# presentation constant, not a game balance value).
LEVEL_COLORS: dict[Literal["ok", "warn", "alert"], str] = {
    "ok": "#00ff00",
    "warn": "#ffff00",
    "alert": "#ff0000",
}

# Block characters (Unicode). U+2588 = full block (filled), U+2591 =
# light shade (empty). These are the htop-style defaults.
_FILLED_CHAR: str = "█"
_EMPTY_CHAR: str = "░"


class MetricBar(Static):
    """htop-styled horizontal metric bar (CPU / MEM / SWAP).

    The bar is exactly ``BAR_WIDTH`` (= 30) characters wide; the filled
    ratio is ``pct / 100``. The foreground color is derived from the
    severity ``level`` via :data:`LEVEL_COLORS`. The bar text follows
    the locked format ``NAME[label_ko]  BAR  XX%  level``.

    The widget is a pure display: callers drive it via
    :meth:`update_value` (typically once per App tick from the
    ``#metrics`` region's data source). The widget itself does NOT
    subscribe to the engine or the EventBus, in keeping with the
    "UI handlers MUST NOT mutate state" invariant from AGENTS.md.
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        """Initialize the bar with a fixed metric name (CPU / MEM / SWAP).

        The initial renderable is an empty string. The actual
        percentage, level, and Korean label are set later via
        :meth:`update_value`. The ``name`` argument is the metric
        identifier (e.g. ``"CPU"``) and appears in the rendered label
        as ``NAME[label_ko]``.
        """
        super().__init__("", **kwargs)
        self._name: str = name
        self._pct: float = 0.0
        self._level: Literal["ok", "warn", "alert"] = "ok"
        self._label_ko: str = ""

    def update_value(
        self,
        pct: float,
        level: Literal["ok", "warn", "alert"],
        label_ko: str,
    ) -> None:
        """Update the bar's value, severity level, and Korean label.

        Given: ``pct`` in [0, 100], ``level`` ∈ {ok, warn, alert}, ``label_ko`` (Korean suffix)
        When: called (typically once per App tick)
        Then: the widget re-renders with the new bar + colors.

        No clamping is applied here: ``MetricsSnapshot`` already clamps
        its percentages to [0, 100]. Out-of-range inputs would produce
        a mis-sized bar; the contract relies on the caller passing
        valid values (mirrors how :func:`compute_metrics` is trusted to
        return sane ints).
        """
        self._pct = pct
        self._level = level
        self._label_ko = label_ko
        self.update(self._build_renderable())

    def _build_renderable(self) -> Text:
        """Build the Rich ``Text`` renderable for the current state.

        Format: ``NAME[label_ko]  BAR  XX%  level`` with two spaces
        between sections. The entire text is colored with the level's
        hex code; the brackets in ``NAME[label_ko]`` are literal
        characters (we build a ``Text`` directly, so Rich markup
        parsing is bypassed and no escaping is needed).
        """
        filled = int(self._pct / 100 * BAR_WIDTH)
        empty = BAR_WIDTH - filled
        bar = _FILLED_CHAR * filled + _EMPTY_CHAR * empty
        body = f"{self._name}[{self._label_ko}]  {bar}  {int(self._pct)}%  {self._level}"
        return Text(body, style=LEVEL_COLORS[self._level])
