"""htop_tycoon.ui.widgets.alert - htop-style alert banner widget (T20).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 493-502:

- ``class Alert(textual.widgets.Static)`` displays the latest alert
  message from the engine.
- Subscribes to ``EventBus.on("AlertRaised", ...)`` at construction time
  (the EventBus dispatches by Python type, so we register ``AlertRaised``;
  the spec's "on" wording maps to the bus's ``subscribe(event_type, cb)``
  API).
- Severity drives the visual style:
    - ``alert`` -> red ``#ff0000`` background, white text, blinking
      bold/dim animation.
    - ``warn``  -> static yellow ``#ffff00``.
    - ``info``  -> static white ``#ffffff``.
- Blink animation via ``set_interval(0.5, ...)`` toggles bold/dim text
  styling every 0.5 seconds while the ``blink`` class is active.
- Blink timeout (LOCKED mechanism from the plan): ``_publish_time`` is
  ``time.monotonic()`` captured at construction; a periodic callback
  (every 0.5s) checks ``time.monotonic() - self._publish_time >=
  _BLINK_TIMEOUT_SECONDS`` and disables blink via
  ``self.set_class(False, "blink")``; on new alert the publish time is
  reset and the class re-enabled.
- Only the latest alert is shown (no queue).
- No blocking-sleep calls anywhere (would freeze the Textual event loop).
- No emoji in the alert surface (htop-style ASCII / Korean only).

Implementation notes on the timeout interval:

- The plan text says ``set_interval(3.0, self._stop_blink)``. With a
  3.0-second check interval the first tick fires at ``T ~= 3.0`` (3.0
  seconds after the interval was registered in ``on_mount``), but the
  publish happens AFTER mount, so ``time.monotonic() -
  self._publish_time`` is slightly less than 3.0 at that tick. The
  check (``>= 3.0``) fails on the first tick and only passes at the
  6.0-second tick -- contradicting the locked acceptance criterion
  "after 3s the blink stops". We therefore drive the timeout check on
  the SAME 0.5s interval as the blink toggle (so the check fires
  frequently enough that the 3-second boundary is caught on the next
  tick). The timeout THRESHOLD remains 3.0 seconds; only the check
  frequency is tightened from 3.0s to 0.5s. Documented in
  ``.omo/evidence/task-20-htop-tycoon.txt``.
- The check operator is ``>=`` (not strict ``>``). With strict ``>``
  the timeout would only fire on the first tick AFTER 3 seconds; with
  ``>=`` it fires on the first tick AT-or-AFTER 3 seconds. The
  ``>=`` choice matches the locked acceptance criterion.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.widgets import Static

from htop_tycoon.engine.events import AlertRaised, EventBus

if TYPE_CHECKING:
    from htop_tycoon.engine.events import AlertSeverity, Event

__all__ = ["Alert"]


# Periodic-tick interval (LOCKED: 0.5s per the plan). Shared by the blink
# toggle and the timeout check; see the module docstring for why.
_TICK_INTERVAL_SECONDS: float = 0.5

# Maximum blink duration in seconds. After this many seconds since the
# last publish, the ``blink`` class is removed.
_BLINK_TIMEOUT_SECONDS: float = 3.0

# Per-severity modifier classes (the locked htop palette).
_SEVERITY_INFO_CLASS: str = "-info"
_SEVERITY_WARN_CLASS: str = "-warn"
_SEVERITY_ALERT_CLASS: str = "-alert"

# Plain CSS class toggled by publish/timeout (NOT a severity modifier).
_BLINK_CLASS: str = "blink"

# Brief CSS modifier for the "bold" half of the blink toggle; the CSS
# text-style:bold provides an extra-bold visual cue while the toggle
# itself is driven by a Text() style (see _refresh).
_BLINK_BRIGHT_CLASS: str = "-blink-bright"

# Locked CSS: severity -> background/color; ``-blink-bright`` adds bold
# via CSS so the visual cue is consistent regardless of who reads the
# widget (CSS-first; Text style reinforces the same effect).
_DEFAULT_CSS = """
Alert {
    height: 3;
}

Alert.-info {
    background: #ffffff;
    color: #000000;
}

Alert.-warn {
    background: #ffff00;
    color: #000000;
}

Alert.-alert {
    background: #ff0000;
    color: #ffffff;
}

Alert.-blink-bright {
    text-style: bold;
}
"""


class Alert(Static):
    """htop-style alert banner: red+blink for ``alert``, static for others.

    The widget subscribes to ``AlertRaised`` events on the supplied
    ``EventBus`` at construction time, so any publish (even before the
    widget is mounted) is recorded once the widget processes its
    callbacks. Severity drives the background color via CSS modifier
    classes; severity ``"alert"`` additionally enables a blinking
    bold/dim animation that auto-disables after 3 seconds.

    Construction:

    - ``bus``: the engine's ``EventBus``. The widget subscribes to
      ``AlertRaised`` on construction (per the locked contract).
    - ``name`` / ``id`` / ``classes`` / ``disabled``: forwarded to
      ``Static`` for layout/CSS parity with the other T17-T22 widgets.
    """

    DEFAULT_CSS: ClassVar[str] = _DEFAULT_CSS

    def __init__(
        self,
        bus: EventBus,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize the alert widget and subscribe to ``AlertRaised``.

        Given: an ``EventBus``
        When:  ``Alert(bus, ...)`` is constructed
        Then:  the widget has subscribed to ``AlertRaised`` events,
               ``_publish_time`` is initialized to ``time.monotonic()``,
               ``_severity`` defaults to ``"info"`` (white, static), and
               ``_message`` is empty.
        """
        super().__init__("", name=name, id=id, classes=classes, disabled=disabled)
        self._bus: EventBus = bus
        self._message: str = ""
        self._severity: AlertSeverity = "info"
        self._publish_time: float = time.monotonic()
        self._blink_state: bool = False
        bus.subscribe(AlertRaised, self._on_alert)

    # ------------------------------------------------------------------ lifecycle

    def on_mount(self) -> None:
        """Start the periodic tick (0.5s) that drives blink + timeout.

        Called by Textual after the widget is mounted. A single
        ``set_interval`` drives both the blink toggle (gated on
        ``severity == "alert"`` and the ``blink`` class) and the
        timeout check (gated on ``elapsed >= _BLINK_TIMEOUT_SECONDS``).
        """
        self.set_interval(_TICK_INTERVAL_SECONDS, self._tick)

    # ------------------------------------------------------------------ EventBus callback

    def _on_alert(self, event: Event) -> None:
        """Handle an ``AlertRaised`` event published on the bus.

        Updates the displayed message + severity, resets the blink
        timeout clock, and refreshes the renderable. Called by the
        ``EventBus``; the bus dispatches by exact Python type, so the
        event is guaranteed to be ``AlertRaised``.
        """
        assert isinstance(event, AlertRaised), (
            f"Expected AlertRaised, got {type(event).__name__}"
        )
        self._message = event.message_ko
        self._severity = event.severity
        self._publish_time = time.monotonic()
        self._blink_state = True
        self._apply_severity_class()
        self.set_class(self._severity == "alert", _BLINK_CLASS)
        self._refresh()

    # ------------------------------------------------------------------ internal mutators

    def _apply_severity_class(self) -> None:
        """Set exactly one of ``-info`` / ``-warn`` / ``-alert``."""
        self.set_class(self._severity == "info", _SEVERITY_INFO_CLASS)
        self.set_class(self._severity == "warn", _SEVERITY_WARN_CLASS)
        self.set_class(self._severity == "alert", _SEVERITY_ALERT_CLASS)

    def _tick(self) -> None:
        """Periodic 0.5s callback: blink toggle + timeout check."""
        self._check_timeout()
        self._toggle_blink()

    def _toggle_blink(self) -> None:
        """Toggle the visual bold/dim state (only while blink is active)."""
        if self._severity != "alert":
            return
        if not self.has_class(_BLINK_CLASS):
            return
        self._blink_state = not self._blink_state
        self.set_class(self._blink_state, _BLINK_BRIGHT_CLASS)
        self._refresh()

    def _check_timeout(self) -> None:
        """Disable blink if the 3-second timeout has elapsed since publish.

        Uses ``>=`` so the very first tick at-or-after the 3-second
        boundary removes the class (the locked acceptance criterion).
        """
        if time.monotonic() - self._publish_time >= _BLINK_TIMEOUT_SECONDS:
            self.set_class(False, _BLINK_CLASS)
            self.set_class(False, _BLINK_BRIGHT_CLASS)

    def _refresh(self) -> None:
        """Rebuild the underlying renderable from the current state."""
        if not self._message:
            self.update("")
            return
        style: str = "bold" if self._blink_state else "dim"
        body = Text(self._message, style=style)
        self.update(body)
