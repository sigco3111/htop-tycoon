"""Engine: EventBus + Event subclasses (one-way Engine->UI).

Locks the contract from .omo/plans/htop-tycoon.md line 319-328:

- Engine-to-UI event dispatch is strictly one-way: the engine calls
  ``bus.publish(event)``; the UI subscribes via ``bus.subscribe`` and
  must NEVER mutate engine state in its callback.
- The bus is a generic dispatcher: subscribers register by Python type
  (``type[Event]``); ``publish`` dispatches to every callback registered
  for ``type(event)``, in registration order.
- ``publish`` is read-only: a callback may call ``subscribe`` or
  ``publish`` during dispatch without affecting the currently-iterating
  dispatch list (the iteration uses a snapshot copy).
- ``publish_many([])`` is a safe no-op.

Event subclasses are frozen dataclasses tagged by their concrete type
(no ``kind`` discriminator needed; the bus dispatches on ``type(event)``).
The 8 documented events are listed in ``__all__`` and re-exported via
``htop_tycoon.engine.__init__``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any, Literal

from htop_tycoon.domain.ending import EndingType
from htop_tycoon.domain.state import (
    CompetitorId,
    EmployeeId,
    GameState,
)

__all__ = [
    "AlertRaised",
    "CompetitorAction",
    "EmployeeDemoted",
    "EmployeeFired",
    "EmployeeHired",
    "EmployeePromoted",
    "EndingTriggered",
    "Event",
    "EventBus",
    "StateUpdated",
]


# ---------------------------------------------------------------------------
# Event base + concrete subclasses (frozen dataclasses, dispatched by type).
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class Event:
    """Base class for all engine-emitted events.

    Concrete events are subclasses; ``EventBus`` dispatches on the exact
    ``type(event)`` (NOT on ``isinstance`` against the base). This means a
    subscriber registered for ``StateUpdated`` will not receive a
    ``StateUpdated`` subclass unless that subclass is registered
    explicitly.
    """


@dataclasses.dataclass(frozen=True, slots=True)
class StateUpdated(Event):
    """Emitted by the engine after every successful state transition.

    Carries the full post-transition ``GameState`` snapshot. UI binds to this
    to refresh its read-only view.
    """

    state: GameState


# Severity literal for AlertRaised; locked to the 3-tier "info/warn/alert"
# scale used throughout the Korean UI footer.
AlertSeverity = Literal["info", "warn", "alert"]


@dataclasses.dataclass(frozen=True, slots=True)
class AlertRaised(Event):
    """A user-facing alert with a Korean message and 3-tier severity.

    Severity semantics:
        - ``info``: routine notice (e.g. budget report).
        - ``warn``: player-actionable warning (e.g. budget 부족).
        - ``alert``: urgent / game-affecting (e.g. bankruptcy warning).
    """

    message_ko: str
    severity: AlertSeverity


@dataclasses.dataclass(frozen=True, slots=True)
class EndingTriggered(Event):
    """An ending condition was met; the UI should show the ending screen.

    Carries the locked ``EndingType`` enum value (BANKRUPTCY, IPO,
    HOSTILE_MA, VOLUNTARY_SALE, SECRET).
    """

    ending_type: EndingType


@dataclasses.dataclass(frozen=True, slots=True)
class EmployeeHired(Event):
    """An employee was hired into a department (T10 hire action)."""

    employee_id: EmployeeId


@dataclasses.dataclass(frozen=True, slots=True)
class EmployeeFired(Event):
    """An employee was fired (F9) with a severance payment."""

    employee_id: EmployeeId
    severance_paid: int


@dataclasses.dataclass(frozen=True, slots=True)
class EmployeePromoted(Event):
    """An employee was promoted (F7)."""

    employee_id: EmployeeId


@dataclasses.dataclass(frozen=True, slots=True)
class EmployeeDemoted(Event):
    """An employee was demoted (F8).

    ``savings_gained`` is the cash the company recouped from the demotion
    (sourced from ``balance.employees.demotion_savings``); defaults to ``0``
    for backward compatibility with earlier construction sites.
    """

    employee_id: EmployeeId
    savings_gained: int = 0


@dataclasses.dataclass(frozen=True, slots=True)
class CompetitorAction(Event):
    """A competitor took an action this tick (T13 competitor AI).

    ``action_type`` is a free-form string (e.g. ``"PRICE_CUT"``,
    ``"TALENT_POACH"``, ``"MARKETING_SPREE"``); the action vocabulary
    lives in ``balance.yaml`` (``competitors.action_costs``).

    ``details`` is a per-action-type payload (default empty dict):
        - ``PRICE_CUT``: ``{"target_product": str, "share_stolen": float}``
        - ``TALENT_POACH``: ``{"target_employee": str | None, "poached": bool,
                                "primary_product": str | None}``
        - ``MARKETING_SPREE``: ``{"cost_paid": int, "share_gained": float}``
            or ``{"skipped": True, "reason": "insufficient_cash"}`` when the
            competitor could not afford the action this tick.
    """

    competitor_id: CompetitorId
    action_type: str
    details: dict[str, Any] = dataclasses.field(default_factory=dict)


# Callback signature: ``Callable[[Event], None]``. The callback receives the
# published event instance by identity (no copy, no transformation).
_EventCallback = Callable[[Event], None]


# ---------------------------------------------------------------------------
# EventBus: generic dispatcher keyed by exact event type.
# ---------------------------------------------------------------------------


class EventBus:
    """One-way engine-to-UI event dispatcher.

    Design contract (locked):

    - ``subscribe(event_type, callback)`` registers ``callback`` to be invoked
      whenever an instance of exactly ``event_type`` is published.
    - ``publish(event)`` invokes every callback registered for
      ``type(event)``, in the order they were registered (FIFO).
    - ``publish`` is READ-ONLY: callbacks may call ``subscribe`` or ``publish``
      without affecting the currently-iterating dispatch (the dispatch
      iterates over a snapshot copy).
    - ``publish_many(events)`` invokes ``publish`` for each event in order;
      ``publish_many([])`` is a no-op.
    - No hard-coded event types: subscribers register by Python ``type``.
    """

    __slots__ = ("_subscribers",)

    def __init__(self) -> None:
        """Initialize the bus with no subscribers."""
        # Maps event type -> ordered list of callbacks (FIFO).
        self._subscribers: dict[type[Event], list[_EventCallback]] = {}

    def subscribe(
        self,
        event_type: type[Event],
        callback: _EventCallback,
    ) -> None:
        """Register ``callback`` to be invoked when an ``event_type`` is published.

        ``event_type`` must be an Event subclass. ``callback`` must be a
        callable accepting a single ``Event`` argument and returning ``None``.
        Subscribing twice to the same event type appends; both callbacks are
        invoked in registration order on the next publish.
        """
        if not isinstance(event_type, type) or not issubclass(event_type, Event):
            raise TypeError(
                f"event_type must be a subclass of Event, got {event_type!r}"
            )
        if not callable(callback):
            raise TypeError(
                f"callback must be callable, got {type(callback).__name__}"
            )
        self._subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event: Event) -> None:
        """Dispatch ``event`` to every subscriber registered for ``type(event)``.

        The dispatch list is snapshotted BEFORE iteration so a callback that
        calls ``subscribe`` or ``publish`` during dispatch does not affect the
        current dispatch (read-only contract).

        Subscribers for unrelated event types are NOT invoked; this is exact-
        type dispatch, not ``isinstance``.
        """
        # Snapshot the callbacks list so mid-dispatch subscribe/publish
        # cannot corrupt the current iteration. The dispatch itself is
        # synchronous (no re-entrancy guard needed beyond the snapshot).
        callbacks = list(self._subscribers.get(type(event), ()))
        for callback in callbacks:
            callback(event)

    def publish_many(self, events: list[Event]) -> None:
        """Dispatch each event in ``events``, in list order.

        ``publish_many([])`` is a no-op (does not invoke any subscriber).
        """
        for event in events:
            self.publish(event)
