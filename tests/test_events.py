"""Tests for T9: EventBus + Event subclasses (one-way Engine->UI).

Locks the contract from .omo/plans/htop-tycoon.md line 319-328:

- ``Event`` subclasses are frozen dataclasses with the documented fields.
- ``EventBus.subscribe(event_type, callback)`` registers a callback for an
  exact event class; ``publish(event)`` invokes every callback registered for
  ``type(event)``, in registration order.
- Subscribing twice to the same event type yields both callbacks being
  invoked in registration order (FIFO).
- ``publish`` is READ-ONLY: callbacks that call ``subscribe`` or ``publish``
  during dispatch must not affect the currently-iterating dispatch list
  (no concurrent-modification / mid-flight mutation).
- ``publish_many([])`` is a safe no-op.
- The bus is a GENERIC dispatcher: it has no hard-coded event types and
  dispatches purely on the Python ``type(event)``.
"""

from __future__ import annotations

import dataclasses

import pytest

from htop_tycoon.domain.ending import EndingType
from htop_tycoon.domain.state import (
    CompetitorId,
    EmployeeId,
    new_game,
)
from htop_tycoon.engine.events import (
    AlertRaised,
    CompetitorAction,
    EmployeeDemoted,
    EmployeeFired,
    EmployeeHired,
    EmployeePromoted,
    EndingTriggered,
    Event,
    EventBus,
    StateUpdated,
)

# -- Event subclasses --------------------------------------------------------


class TestEventSubclasses:
    """Each Event subclass is a frozen dataclass with the documented fields."""

    def test_state_updated_carries_state(self) -> None:
        """StateUpdated holds the full GameState snapshot."""
        s = new_game(42)
        e = StateUpdated(state=s)
        assert e.state is s
        assert dataclasses.is_dataclass(e)
        assert e in (e,)  # eq by identity for frozen dataclass

    def test_alert_raised_severity_literal(self) -> None:
        """AlertRaised requires severity in {"info","warn","alert"}."""
        e = AlertRaised(message_ko="주의", severity="warn")
        assert e.message_ko == "주의"
        assert e.severity == "warn"

    def test_alert_raised_is_frozen(self) -> None:
        """AlertRaised must be frozen (no late mutation)."""
        e = AlertRaised(message_ko="주의", severity="warn")
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.message_ko = "다른"  # type: ignore[misc]

    def test_ending_triggered_carries_ending_type(self) -> None:
        """EndingTriggered carries an EndingType enum value."""
        e = EndingTriggered(ending_type=EndingType.IPO)
        assert e.ending_type is EndingType.IPO

    def test_employee_hired_carries_employee_id(self) -> None:
        """EmployeeHired carries an EmployeeId."""
        e = EmployeeHired(employee_id=EmployeeId("emp-001"))
        assert e.employee_id == "emp-001"

    def test_employee_fired_carries_id_and_severance(self) -> None:
        """EmployeeFired carries employee_id + severance_paid (int)."""
        e = EmployeeFired(
            employee_id=EmployeeId("emp-007"),
            severance_paid=4_000,
        )
        assert e.employee_id == "emp-007"
        assert e.severance_paid == 4_000

    def test_employee_promoted_carries_employee_id(self) -> None:
        """EmployeePromoted carries an EmployeeId."""
        e = EmployeePromoted(employee_id=EmployeeId("emp-002"))
        assert e.employee_id == "emp-002"

    def test_employee_demoted_carries_employee_id(self) -> None:
        """EmployeeDemoted carries an EmployeeId."""
        e = EmployeeDemoted(employee_id=EmployeeId("emp-003"))
        assert e.employee_id == "emp-003"

    def test_employee_demoted_carries_savings_gained(self) -> None:
        """EmployeeDemoted carries savings_gained (int) — T10 demote return shape."""
        e = EmployeeDemoted(
            employee_id=EmployeeId("emp-004"),
            savings_gained=300,
        )
        assert e.employee_id == "emp-004"
        assert e.savings_gained == 300
        assert isinstance(e.savings_gained, int)

    def test_employee_demoted_savings_gained_defaults_to_zero(self) -> None:
        """EmployeeDemoted.savings_gained defaults to 0 for backward compat."""
        e = EmployeeDemoted(employee_id=EmployeeId("emp-005"))
        assert e.savings_gained == 0

    def test_competitor_action_carries_id_and_type(self) -> None:
        """CompetitorAction carries competitor_id + action_type (str)."""
        e = CompetitorAction(
            competitor_id=CompetitorId("comp-1"),
            action_type="PRICE_CUT",
        )
        assert e.competitor_id == "comp-1"
        assert e.action_type == "PRICE_CUT"

    def test_all_events_inherit_event(self) -> None:
        """Every concrete event subclass shares the Event base (isinstance check)."""
        for ev in (
            StateUpdated(state=new_game(42)),
            AlertRaised(message_ko="x", severity="info"),
            EndingTriggered(ending_type=EndingType.BANKRUPTCY),
            EmployeeHired(employee_id=EmployeeId("e1")),
            EmployeeFired(employee_id=EmployeeId("e1"), severance_paid=0),
            EmployeePromoted(employee_id=EmployeeId("e1")),
            EmployeeDemoted(employee_id=EmployeeId("e1")),
            CompetitorAction(competitor_id=CompetitorId("c1"), action_type="X"),
        ):
            assert isinstance(ev, Event)


# -- EventBus subscribe + publish -------------------------------------------


class TestEventBusSubscribePublish:
    """subscribe + publish dispatches to the matching subscriber."""

    def test_subscribe_then_publish_invokes_callback(self) -> None:
        """Given: a bus subscribed to StateUpdated with a recording callback
        When: a StateUpdated event is published
        Then: the callback receives the event exactly once
        """
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe(StateUpdated, received.append)
        state = new_game(42)
        bus.publish(StateUpdated(state=state))
        assert received == [StateUpdated(state=state)]

    def test_publish_without_subscriber_is_noop(self) -> None:
        """Given: an empty bus
        When: any event is published
        Then: nothing happens (no error, no callback)
        """
        bus = EventBus()
        # Must not raise.
        bus.publish(AlertRaised(message_ko="hi", severity="info"))

    def test_callback_receives_exact_event_object(self) -> None:
        """publish must pass the published event instance to the callback
        (identity, not a copy). The UI binds to it.
        """
        bus = EventBus()
        seen: list[AlertRaised] = []
        bus.subscribe(AlertRaised, seen.append)
        event = AlertRaised(message_ko="경고", severity="alert")
        bus.publish(event)
        assert seen[0] is event


# -- Registration order -----------------------------------------------------


class TestEventBusRegistrationOrder:
    """Subscribing twice to the same event type yields both callbacks in FIFO."""

    def test_double_subscribe_invokes_both_in_order(self) -> None:
        """Given: two callbacks registered for StateUpdated, in order
        When: a StateUpdated is published
        Then: both fire, in registration order (FIFO)
        """
        bus = EventBus()
        order: list[str] = []
        bus.subscribe(StateUpdated, lambda _e: order.append("first"))
        bus.subscribe(StateUpdated, lambda _e: order.append("second"))
        bus.publish(StateUpdated(state=new_game(1)))
        assert order == ["first", "second"]

    def test_different_event_types_are_isolated(self) -> None:
        """A subscriber to StateUpdated must NOT receive AlertRaised events."""
        bus = EventBus()
        seen_state: list[Event] = []
        seen_alert: list[Event] = []
        bus.subscribe(StateUpdated, seen_state.append)
        bus.subscribe(AlertRaised, seen_alert.append)
        bus.publish(AlertRaised(message_ko="x", severity="info"))
        assert seen_state == []
        assert len(seen_alert) == 1


# -- publish is read-only ---------------------------------------------------


class TestEventBusReadOnly:
    """publish is read-only: callbacks may not mutate the bus during dispatch."""

    def test_callback_may_not_mutate_current_dispatch_list(self) -> None:
        """Given: a callback that calls subscribe() while publish is iterating
        When: publish runs the callback
        Then: the newly-subscribed callback does NOT fire on the SAME publish
              (no concurrent modification; the current dispatch list is a copy)
        """
        bus = EventBus()
        main_fired: list[bool] = []
        late_fired: list[bool] = []

        def during_publish(_event: Event) -> None:
            main_fired.append(True)
            # Mid-dispatch mutation: register a new callback for StateUpdated.
            bus.subscribe(StateUpdated, lambda _e: late_fired.append(True))

        bus.subscribe(StateUpdated, during_publish)
        bus.publish(StateUpdated(state=new_game(7)))
        # The "during" callback fired, but the late one did NOT fire on this
        # publish (it will fire on a subsequent publish).
        assert main_fired == [True]
        assert late_fired == []

    def test_late_subscription_fires_on_subsequent_publish(self) -> None:
        """A callback subscribed during a prior publish() fires on the NEXT publish."""
        bus = EventBus()
        late_fired: list[bool] = []

        def during_publish(_event: Event) -> None:
            bus.subscribe(StateUpdated, lambda _e: late_fired.append(True))

        bus.subscribe(StateUpdated, during_publish)
        bus.publish(StateUpdated(state=new_game(7)))  # late registers here
        bus.publish(StateUpdated(state=new_game(7)))  # late fires here
        assert late_fired == [True]

    def test_callback_may_publish_other_event_without_recursion(self) -> None:
        """A callback may call bus.publish() for a different event type
        (no recursion on the same dispatch); the inner publish completes first.
        """
        bus = EventBus()
        inner_alerts: list[AlertRaised] = []
        bus.subscribe(AlertRaised, inner_alerts.append)

        def outer(_event: Event) -> None:
            bus.publish(AlertRaised(message_ko="from-outer", severity="warn"))

        bus.subscribe(StateUpdated, outer)
        bus.publish(StateUpdated(state=new_game(1)))
        assert len(inner_alerts) == 1
        assert inner_alerts[0].message_ko == "from-outer"


# -- publish_many -----------------------------------------------------------


class TestEventBusPublishMany:
    """publish_many([]) is a safe no-op; publish_many([..]) dispatches each."""

    def test_publish_many_empty_is_noop(self) -> None:
        """publish_many([]) does not invoke any subscriber."""
        bus = EventBus()
        seen: list[Event] = []
        bus.subscribe(StateUpdated, seen.append)
        bus.subscribe(AlertRaised, seen.append)
        bus.publish_many([])
        assert seen == []

    def test_publish_many_dispatches_each_in_order(self) -> None:
        """publish_many dispatches every event in the list, in list order."""
        bus = EventBus()
        seen: list[Event] = []
        bus.subscribe(StateUpdated, seen.append)
        bus.subscribe(AlertRaised, seen.append)
        s = new_game(42)
        events = [
            StateUpdated(state=s),
            AlertRaised(message_ko="a", severity="info"),
            AlertRaised(message_ko="b", severity="warn"),
        ]
        bus.publish_many(events)
        assert len(seen) == 3
        assert seen[0] is events[0]
        assert seen[1] is events[1]
        assert seen[2] is events[2]


# -- Generic dispatcher (no hard-coded types) -------------------------------


class TestEventBusGenericDispatcher:
    """The bus dispatches purely on Python type(event); no hard-coded mapping."""

    def test_custom_subclass_dispatches_via_subclass(self) -> None:
        """A custom Event subclass dispatches via its own type registration."""

        @dataclasses.dataclass(frozen=True, slots=True)
        class MyCustomEvent(Event):
            payload: str

        bus = EventBus()
        seen: list[MyCustomEvent] = []
        bus.subscribe(MyCustomEvent, seen.append)
        event = MyCustomEvent(payload="hello")
        bus.publish(event)
        assert seen == [event]

    def test_bus_does_not_dispatch_to_parent_subscribers(self) -> None:
        """Subscribing to the Event base class does NOT receive a subclass event.
        The bus dispatches on the EXACT type, not on isinstance().
        """
        bus = EventBus()
        seen: list[Event] = []
        bus.subscribe(Event, seen.append)
        bus.publish(StateUpdated(state=new_game(42)))
        assert seen == []
