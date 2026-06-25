"""Tests for T20: Alert widget (blink animation, EventBus wired, timeout).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 493-502:

- ``class Alert(Static)`` displays the latest alert message.
- Subscribes to ``EventBus.on("AlertRaised", ...)`` at construction time
  (the EventBus dispatches by Python type, so we register ``AlertRaised``).
- Severity drives the visual style:
    - ``alert`` -> red ``#ff0000`` background, white text, blinking bold/dim.
    - ``warn``  -> static yellow ``#ffff00``.
    - ``info``  -> static white ``#ffffff``.
- Blink timeout (LOCKED mechanism from the plan):
    - ``_publish_time: float = time.monotonic()`` is reset on every new alert.
    - ``set_interval(3.0, self._stop_blink)`` checks
      ``time.monotonic() - self._publish_time >= 3.0`` and disables blink via
      ``self.set_class(False, "blink")``.
    - On new alert, ``_publish_time`` is reset and the ``blink`` class is
      re-enabled.
- Only the latest alert is shown (no queue).
- No ``time.sleep`` anywhere (it would block the Textual event loop).
- No emoji in alert messages (htop-style ASCII / Korean only).

Pilot tests use ``asyncio.sleep(seconds)`` to advance wall-clock time
so Textual's interval timers (which fire on the asyncio loop) tick
naturally. ``pilot.pause()`` is called after each ``asyncio.sleep`` to
flush any pending messages.
"""

from __future__ import annotations

import asyncio
import inspect

from textual.app import App

from htop_tycoon.engine.events import AlertRaised, EventBus
from htop_tycoon.ui.widgets.alert import Alert

# -- Pilot host App --------------------------------------------------------


class _AlertHostApp(App[None]):
    """Minimal App that mounts a single ``Alert`` widget.

    The widget is constructed BEFORE the App runs so the subscription to
    the EventBus happens at construction time (per the spec contract).
    """

    def __init__(self, alert: Alert) -> None:
        super().__init__()
        self._alert = alert

    def compose(self) -> object:
        yield self._alert


def _plain(alert: Alert) -> str:
    """Return the alert's renderable as plain text (no markup/colors).

    Mirrors ``_plain`` from ``test_metric_bar_pilot.py``: bypass the
    visual wrapper and read the underlying ``Text`` (or str) directly.
    """
    renderable = alert.renderable  # type: ignore[no-any-return]
    plain_attr = getattr(renderable, "plain", None)
    if plain_attr is not None:
        return str(plain_attr)
    return str(renderable)


# -- Module surface --------------------------------------------------------


def test_alert_module_exposes_class() -> None:
    """``alert`` module is importable and exposes the ``Alert`` class."""
    import htop_tycoon.ui.widgets.alert as mod

    assert hasattr(mod, "Alert")


def test_alert_subclasses_static() -> None:
    """``Alert`` subclasses ``textual.widgets.Static`` (widget contract)."""
    from textual.widgets import Static

    assert issubclass(Alert, Static)


def test_alert_is_exported_from_widgets_package() -> None:
    """``Alert`` is re-exported from ``htop_tycoon.ui.widgets`` (additive)."""
    from htop_tycoon.ui.widgets import Alert as ReExported

    assert ReExported is Alert


# -- Construction-time subscription ----------------------------------------


class TestAlertSubscription:
    """``Alert`` subscribes to ``AlertRaised`` events at construction time."""

    async def test_subscription_at_construction_receives_publish(self) -> None:
        """Given: an Alert constructed with a bus (NOT pre-subscribed externally)
        When: AlertRaised is published via the bus
        Then: the widget renders the alert message.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("오늘 마감이요!", "alert"))
            await pilot.pause()
            assert "오늘 마감이요!" in _plain(alert)

    async def test_widget_does_not_subscribe_to_other_event_types(self) -> None:
        """The widget only listens for ``AlertRaised`` (exact-type dispatch).

        Publishing a different event must NOT trigger the alert callback.
        """
        from htop_tycoon.domain.state import new_game
        from htop_tycoon.engine.events import StateUpdated

        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(StateUpdated(new_game(42)))
            await pilot.pause()
            # No alert message should be set.
            assert _plain(alert) == ""


# -- Severity -> CSS class state ------------------------------------------


class TestAlertSeverityClasses:
    """Each severity applies the locked modifier class."""

    async def test_alert_severity_applies_alert_class_and_blink(self) -> None:
        """Given: Alert(bus)
        When: AlertRaised(severity='alert') is published
        Then: ``-alert`` and ``blink`` classes are set on the widget.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("마감 임박", "alert"))
            await pilot.pause()
            assert alert.has_class("-alert")
            assert alert.has_class("blink")

    async def test_warn_severity_applies_warn_class_no_blink(self) -> None:
        """Given: Alert(bus)
        When: AlertRaised(severity='warn') is published
        Then: ``-warn`` class is set; ``blink`` class is NOT set.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("예산 부족", "warn"))
            await pilot.pause()
            assert alert.has_class("-warn")
            assert not alert.has_class("-alert")
            assert not alert.has_class("blink")

    async def test_info_severity_applies_info_class_no_blink(self) -> None:
        """Given: Alert(bus)
        When: AlertRaised(severity='info') is published
        Then: ``-info`` class is set; ``blink`` class is NOT set (white bg).
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("공지사항", "info"))
            await pilot.pause()
            assert alert.has_class("-info")
            assert not alert.has_class("-warn")
            assert not alert.has_class("-alert")
            assert not alert.has_class("blink")


# -- Only the latest alert is shown ---------------------------------------


class TestAlertLatestOnly:
    """A second publish replaces the first (no queue)."""

    async def test_second_publish_replaces_first_message(self) -> None:
        """Given: an alert showing the first message
        When: a second alert is published
        Then: the widget shows the new message only.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("첫번째", "alert"))
            await pilot.pause()
            bus.publish(AlertRaised("두번째", "warn"))
            await pilot.pause()
            text = _plain(alert)
            assert "두번째" in text
            assert "첫번째" not in text


# -- Blink timeout mechanism (LOCKED) --------------------------------------


class TestAlertBlinkTimeout:
    """The ``blink`` class is removed after the 3-second timeout fires."""

    async def test_blink_class_present_immediately_after_publish(self) -> None:
        """Given: a freshly-mounted Alert
        When: AlertRaised(severity='alert') is published
        Then: the ``blink`` class is present immediately.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("오늘 마감이요!", "alert"))
            await pilot.pause()
            assert alert.has_class("blink")

    async def test_blink_class_still_present_at_0_6s(self) -> None:
        """Plan acceptance: 'waits 0.6s, asserts widget has blink class'.

        The 0.5s blink-toggler must fire, but the 3.0s timeout must NOT
        yet have fired. The ``blink`` class persists for the full 3s.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("오늘 마감이요!", "alert"))
            await pilot.pause()
            await asyncio.sleep(0.6)
            await pilot.pause()
            assert alert.has_class("blink")

    async def test_blink_class_removed_after_3s_timeout(self) -> None:
        """Plan acceptance: 'Waits another 3s, asserts blink class removed'.

        After 0.6s + 3.0s = 3.6s total, the 3.0s timeout has fired and
        removed the blink class.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("오늘 마감이요!", "alert"))
            await pilot.pause()
            await asyncio.sleep(3.5)
            await pilot.pause()
            assert not alert.has_class("blink")

    async def test_severity_class_persists_after_blink_timeout(self) -> None:
        """The ``-alert`` modifier persists after blink stops.

        Only the blink visual effect stops; the severity-driven styling
        remains so the widget still reads as a red alert after the 3s.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("지속", "alert"))
            await pilot.pause()
            await asyncio.sleep(3.5)
            await pilot.pause()
            assert alert.has_class("-alert")
            assert not alert.has_class("blink")

    async def test_new_alert_after_timeout_re_enables_blink(self) -> None:
        """Given: a previously-blinking alert that has timed out
        When: a new alert is published
        Then: the ``blink`` class is re-enabled and the timer resets.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("First", "alert"))
            await pilot.pause()
            await asyncio.sleep(3.5)
            await pilot.pause()
            assert not alert.has_class("blink")
            # New alert resets the timer.
            bus.publish(AlertRaised("Second", "alert"))
            await pilot.pause()
            assert alert.has_class("blink")
            # Still blinking after another 2s (well under the 3s timeout).
            await asyncio.sleep(2.0)
            await pilot.pause()
            assert alert.has_class("blink")

    async def test_new_alert_resets_timer_mid_blink(self) -> None:
        """Given: an alert that has been blinking for 2s
        When: a new alert is published
        Then: the timer resets so blink persists past the original 3s mark.
        """
        bus = EventBus()
        alert = Alert(bus, id="alert")
        app = _AlertHostApp(alert)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(AlertRaised("First", "alert"))
            await pilot.pause()
            await asyncio.sleep(2.0)
            await pilot.pause()
            assert alert.has_class("blink")
            # New alert resets the timer at T=2s. Wait another 2.5s so total
            # elapsed since the FIRST publish is 4.5s, but since the SECOND
            # publish was at T=2s, only 2.5s have elapsed for it — blink
            # should still be present.
            bus.publish(AlertRaised("Second", "alert"))
            await pilot.pause()
            await asyncio.sleep(2.5)
            await pilot.pause()
            assert alert.has_class("blink")


# -- Anti-pattern: no time.sleep ------------------------------------------


def test_alert_module_does_not_use_time_sleep() -> None:
    """The Alert module must NOT call ``time.sleep`` (blocks Textual loop)."""
    import htop_tycoon.ui.widgets.alert as mod

    source = inspect.getsource(mod)
    assert "time.sleep(" not in source, (
        "Alert module must use Textual's set_interval for blink/timeout, "
        "not time.sleep (which would block the event loop)."
    )


def test_alert_module_does_not_use_emoji() -> None:
    """Alert messages + module source must NOT contain emoji.

    Per AGENTS.md: 'No emoji anywhere in source, docs, README headers,
    or in commit messages.' Alert is htop-style ASCII / Korean only.
    """
    import htop_tycoon.ui.widgets.alert as mod

    source = inspect.getsource(mod)
    # Spot-check a small set of common emoji code points; this is a
    # fast-fail lint, not an exhaustive detector.
    forbidden = ["\U0001f600", "\u2728", "\u26a0", "\U0001f525", "\U0001f514"]
    for emoji in forbidden:
        assert emoji not in source, (
            f"Alert module contains forbidden emoji: {emoji!r}"
        )
