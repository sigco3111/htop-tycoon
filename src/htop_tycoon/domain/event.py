"""Domain: Event, Effect (tagged union), StoryNode, Choice.

Contracts (locked by .omo/plans/htop-tycoon.md line 265-280):

- ``Event`` is a frozen dataclass carrying id, Korean name/description,
  a random/conditional trigger, a per-tick probability, an optional
  condition predicate, and a tuple of ``Effect`` payloads to apply.
- ``Effect`` is a discriminated union over six concrete frozen dataclasses
  sharing a string ``kind`` discriminator. The engine dispatches on ``kind``.
- ``StoryNode`` carries id, Korean prompt, an ordered tuple of ``Choice``s,
  and an ``on_choose`` callback invoked when the player picks a choice.
- Concrete event chains live in ``events.yaml`` (T14); this module is data only.

A separate ``Choice.next_node_id`` of ``None`` marks a terminal node (end of
branch). ``TriggerSecretInvestor`` is a marker effect: it does NOT flip
``state.secret_investor_cleared`` — that flag is reserved for player resolution.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any, Literal

from htop_tycoon.domain.ending import EndingType
from htop_tycoon.domain.state import (
    DepartmentId,
    EmployeeId,
    EventId,
    GameState,
    ProductId,
    StoryNodeId,
)

__all__ = [
    "AddEmployee",
    "BoostRevenue",
    "Choice",
    "Effect",
    "Event",
    "EventCondition",
    "RemoveEmployee",
    "ScheduleEnding",
    "ScheduleNextEvent",
    "ShiftMarketShare",
    "StoryNode",
    "StoryOnChoose",
    "TriggerSecretInvestor",
]


# ---------------------------------------------------------------------------
# Effects — discriminated union keyed on the ``kind`` Literal field.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class AddEmployee:
    """Spawn a new employee in the given department (engine generates the name)."""

    kind: Literal["add_employee"]
    dept_id: DepartmentId


@dataclasses.dataclass(frozen=True, slots=True)
class RemoveEmployee:
    """Remove the employee identified by ``employee_id`` (e.g. quit / fired-by-event)."""

    kind: Literal["remove_employee"]
    employee_id: EmployeeId


@dataclasses.dataclass(frozen=True, slots=True)
class ShiftMarketShare:
    """Nudge the market share of a product by ``delta`` (may be negative)."""

    kind: Literal["shift_market_share"]
    product_id: ProductId
    delta: float


@dataclasses.dataclass(frozen=True, slots=True)
class BoostRevenue:
    """Apply a one-shot revenue boost of ``amount`` (int, may be negative)."""

    kind: Literal["boost_revenue"]
    product_id: ProductId
    amount: int


@dataclasses.dataclass(frozen=True, slots=True)
class TriggerSecretInvestor:
    """Mark the secret-investor story as TRIGGERED (pending player choice).

    This effect carries NO reference to ``state.secret_investor_cleared``.
    That flag is flipped only by the player-resolution handler; until then,
    the secret investor is merely *pending*. The engine applying this
    effect updates a transient pending flag — never the cleared flag.
    """

    kind: Literal["trigger_secret_investor"]


@dataclasses.dataclass(frozen=True, slots=True)
class ScheduleEnding:
    """Schedule a specific ending to be evaluated at the next tick."""

    kind: Literal["schedule_ending"]
    ending_type: EndingType


@dataclasses.dataclass(frozen=True, slots=True)
class ScheduleNextEvent:
    """Schedule a follow-up event in the chain (T14).

    Carries the id of the event to fire next. The event_chain engine reads
    this effect when a parent event fires, then schedules the named event
    at chain_depth + 1 (truncated by ``balance.events.max_concurrent_chain_depth``).

    This effect is a control-flow directive ONLY; it carries no state mutation
    payload of its own. It is the 7th and final variant of the Effect union.
    """

    kind: Literal["schedule_next_event"]
    event_id: EventId


# Union of all effect types. The runtime discriminator is ``effect.kind``;
# the engine uses ``match``/``case`` for exhaustive dispatch.
Effect = (
    AddEmployee
    | RemoveEmployee
    | ShiftMarketShare
    | BoostRevenue
    | TriggerSecretInvestor
    | ScheduleEnding
    | ScheduleNextEvent
)


# ---------------------------------------------------------------------------
# Event + its condition callback signature.
# ---------------------------------------------------------------------------


# A condition is ``(state, ctx) -> bool`` where ctx is the same EvaluationContext
# used by ending evaluators. ``None`` means the trigger is purely random
# (governed by ``probability_per_tick``).
EventCondition = Callable[[GameState, Any], bool] | None


@dataclasses.dataclass(frozen=True, slots=True)
class Event:
    """A domain event. Data only — the engine decides when to fire it.

    Attributes:
        id: Stable identifier (e.g. ``"evt-key-employee-quit"``).
        name_ko: Korean short title shown in the UI.
        description_ko: Korean description / flavor text.
        trigger_type: ``"random"`` (per-tick probability) or ``"conditional"``
            (must satisfy ``condition`` to fire).
        probability_per_tick: Per-tick probability when ``trigger_type ==
            "random"``. Zero when ``trigger_type == "conditional"``.
        condition: Optional predicate ``(state, ctx) -> bool``. ``None`` for
            pure-random events.
        effects: Ordered tuple of ``Effect`` payloads to apply when fired.
    """

    id: EventId
    name_ko: str
    description_ko: str
    trigger_type: Literal["random", "conditional"]
    probability_per_tick: float
    condition: EventCondition
    effects: tuple[Effect, ...]


# ---------------------------------------------------------------------------
# StoryNode + Choice.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class Choice:
    """A single story choice: a Korean label and (optionally) the next node.

    ``next_node_id is None`` means this choice ends the current branch
    (a terminal / leaf node).
    """

    label_ko: str
    next_node_id: StoryNodeId | None = None


# ``on_choose(choice) -> Any`` is invoked with the picked ``Choice``; the
# return value is opaque to ``StoryNode`` itself (engine interprets it).
StoryOnChoose = Callable[[Choice], Any]


@dataclasses.dataclass(frozen=True, slots=True)
class StoryNode:
    """A single beat in a branching Korean-language story.

    Attributes:
        id: Stable identifier.
        prompt_ko: Korean prompt shown to the player.
        choices: Ordered, non-empty tuple of ``Choice`` payloads.
        on_choose: Callback invoked with the picked ``Choice``.
    """

    id: StoryNodeId
    prompt_ko: str
    choices: tuple[Choice, ...]
    on_choose: StoryOnChoose
