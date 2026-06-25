"""Engine: Event chain evaluation + YAML catalog loading (T14).

Locks the contract from .omo/plans/htop-tycoon.md line 406-415:

- ``load_events_catalog(path=None)`` parses ``events.yaml`` into a typed
  ``list[Event]``. Every ``condition`` string MUST resolve in
  ``CONDITION_REGISTRY``; unresolved conditions raise ``ValueError`` at
  load time (fail-loud, no silent skip). Every effect dict is parsed into
  the ``Effect`` discriminated union (7 variants including
  ``ScheduleNextEvent`` for chains); unknown effect types raise ``ValueError``.

- ``evaluate_events(state, rng, balance, events_catalog, active_events)``
  evaluates triggers each tick, applies effects to the state, returns the
  updated state plus a list of fired events plus the updated
  ``active_events`` list.

- Chains: events can schedule follow-up events via the ``ScheduleNextEvent``
  effect (max chain depth from ``balance.events.max_concurrent_chain_depth``,
  default 4). Events that are TARGETS of ``ScheduleNextEvent`` are
  considered "chain-only" — they do NOT fire on their own as catalog
  triggers; they fire only when reached via a chain.

- The engine NEVER publishes events to the dispatcher. Pure functions return
  ``(new_state, fired_events, new_active_events)`` and let the caller publish.

Determinism: ``GameRNG`` is the single sanctioned adapter for randomness;
no ``random.*`` calls here.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from htop_tycoon.domain.event import (
    AddEmployee,
    BoostRevenue,
    Effect,
    Event,
    EventCondition,
    RemoveEmployee,
    ScheduleEnding,
    ScheduleNextEvent,
    ShiftMarketShare,
    TriggerSecretInvestor,
)
from htop_tycoon.domain.state import EventId, GameState, ProductId
from htop_tycoon.engine.condition_registry import CONDITION_REGISTRY
from htop_tycoon.engine.rng import GameRNG

__all__ = [
    "EventInstance",
    "evaluate_events",
    "load_events_catalog",
]


# ---------------------------------------------------------------------------
# EventInstance — wraps an Event with its current chain depth.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class EventInstance:
    """A scheduled event with chain-depth tracking.

    ``chain_depth == 0`` means the event was a top-level trigger (random
    or conditional from the catalog); higher values mean the event was
    scheduled via a ``ScheduleNextEvent`` chain effect.

    The chain-depth cap is read from
    ``balance.events.max_concurrent_chain_depth`` (default 4 levels,
    depths 0..max-1). ``evaluate_events`` enforces the cap; depth >= max
    is silently truncated (the dropped follow-up is NOT re-queued).
    """

    event: Event
    chain_depth: int


# ---------------------------------------------------------------------------
# YAML catalog loader.
# ---------------------------------------------------------------------------


# Effect-kind dispatcher: maps YAML ``type`` discriminator → Effect class.
# Each entry knows how to build a typed Effect from a parsed dict.
_EffectBuilder = Callable[[dict[str, Any]], Effect]


def _build_shift_market_share(d: dict[str, Any]) -> Effect:
    return ShiftMarketShare(
        kind="shift_market_share",
        product_id=ProductId(str(d["product_id"])),
        delta=float(d["delta"]),
    )


def _build_boost_revenue(d: dict[str, Any]) -> Effect:
    return BoostRevenue(
        kind="boost_revenue",
        product_id=ProductId(str(d["product_id"])),
        amount=int(d["amount"]),
    )


def _build_trigger_secret_investor(d: dict[str, Any]) -> Effect:
    return TriggerSecretInvestor(kind="trigger_secret_investor")


def _build_schedule_ending(d: dict[str, Any]) -> Effect:
    from htop_tycoon.domain.ending import EndingType

    return ScheduleEnding(
        kind="schedule_ending",
        ending_type=EndingType(str(d["ending_type"])),
    )


def _build_schedule_next_event(d: dict[str, Any]) -> Effect:
    return ScheduleNextEvent(
        kind="schedule_next_event",
        event_id=EventId(str(d["event_id"])),
    )


def _build_add_employee(d: dict[str, Any]) -> Effect:
    from htop_tycoon.domain.state import DepartmentId

    return AddEmployee(
        kind="add_employee",
        dept_id=DepartmentId(str(d["dept_id"])),
    )


def _build_remove_employee(d: dict[str, Any]) -> Effect:
    from htop_tycoon.domain.state import EmployeeId

    return RemoveEmployee(
        kind="remove_employee",
        employee_id=EmployeeId(str(d["employee_id"])),
    )


# Registry of effect-type → builder. Lookup at parse time.
_EFFECT_BUILDERS: dict[str, _EffectBuilder] = {
    "shift_market_share": _build_shift_market_share,
    "boost_revenue": _build_boost_revenue,
    "trigger_secret_investor": _build_trigger_secret_investor,
    "schedule_ending": _build_schedule_ending,
    "schedule_next_event": _build_schedule_next_event,
    "add_employee": _build_add_employee,
    "remove_employee": _build_remove_employee,
}


def _parse_effect(effect_dict: dict[str, Any]) -> Effect:
    """Parse a single effect dict from yaml into a typed Effect.

    Raises:
        ValueError: if ``type`` is missing, unknown, or required params
            are absent / wrong-typed.
    """
    if "type" not in effect_dict:
        raise ValueError(f"effect dict missing 'type' discriminator: {effect_dict!r}")
    eff_type = str(effect_dict["type"])
    builder = _EFFECT_BUILDERS.get(eff_type)
    if builder is None:
        raise ValueError(
            f"unknown effect type {eff_type!r}; "
            f"known types: {sorted(_EFFECT_BUILDERS.keys())}"
        )
    return builder(effect_dict)


def _parse_condition(condition: Any) -> EventCondition:
    """Resolve a YAML ``condition`` value to a callable.

    ``None`` and YAML null -> ``None`` (random trigger only).
    A string -> must match a key in ``CONDITION_REGISTRY``; otherwise
    ``ValueError`` is raised at load time (fail-loud).
    """
    if condition is None:
        return None
    if isinstance(condition, str):
        cond_name = condition
        if cond_name not in CONDITION_REGISTRY:
            raise ValueError(
                f"condition {cond_name!r} is not registered in CONDITION_REGISTRY; "
                f"known conditions: {sorted(CONDITION_REGISTRY.keys())}"
            )
        return CONDITION_REGISTRY[cond_name]
    raise ValueError(
        f"condition must be null or a registry name (str), got {type(condition).__name__}"
    )


def _parse_event_dict(event_dict: dict[str, Any]) -> Event:
    """Parse a single event dict from yaml into a typed Event.

    Raises:
        ValueError: on missing required fields, unknown effect types, or
            unregistered condition names.
    """
    required = (
        "id", "name_ko", "description_ko", "trigger_type",
        "probability_per_tick", "effects",
    )
    missing = [k for k in required if k not in event_dict]
    if missing:
        raise ValueError(
            f"event dict missing required fields {missing!r}: {event_dict!r}"
        )

    trigger_type = str(event_dict["trigger_type"])
    if trigger_type not in ("random", "conditional"):
        raise ValueError(
            f"trigger_type must be 'random' or 'conditional', got {trigger_type!r}"
        )

    probability = float(event_dict["probability_per_tick"])
    if not 0.0 <= probability <= 1.0:
        raise ValueError(
            f"probability_per_tick must be in [0.0, 1.0], got {probability!r}"
        )

    effects_raw = event_dict["effects"]
    if not isinstance(effects_raw, list):
        raise ValueError(
            f"effects must be a list, got {type(effects_raw).__name__}"
        )
    effects: tuple[Effect, ...] = tuple(_parse_effect(eff) for eff in effects_raw)

    condition: EventCondition = _parse_condition(event_dict.get("condition"))

    return Event(
        id=EventId(str(event_dict["id"])),
        name_ko=str(event_dict["name_ko"]),
        description_ko=str(event_dict["description_ko"]),
        trigger_type=trigger_type,  # type: ignore[arg-type]
        probability_per_tick=probability,
        condition=condition,
        effects=effects,
    )


def load_events_catalog(path: Path | None = None) -> list[Event]:
    """Load ``events.yaml`` into a typed list of ``Event`` objects.

    The default path is ``src/htop_tycoon/data/events.yaml`` (the shipped
    catalog). Tests may pass a custom path to load synthetic catalogs.

    Returns:
        A list of typed ``Event`` instances, in YAML declaration order.

    Raises:
        ValueError: if any ``condition`` name is not in
            ``CONDITION_REGISTRY``, if any effect ``type`` is unknown, or if
            any event is missing a required field.
        FileNotFoundError: if the default path is used and the file is missing.
    """
    yaml_path = path if path is not None else Path(__file__).parent.parent / "data" / "events.yaml"
    with yaml_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise TypeError(
            f"events.yaml root must be a mapping, got {type(raw).__name__}"
        )
    events_list = raw.get("events")
    if not isinstance(events_list, list):
        raise TypeError(
            f"events.yaml must contain an 'events' list, got {type(events_list).__name__}"
        )
    return [_parse_event_dict(entry) for entry in events_list]


# ---------------------------------------------------------------------------
# Trigger evaluation.
# ---------------------------------------------------------------------------


def _event_triggers(
    event: Event,
    state: GameState,
    balance: dict[str, Any],
    rng: GameRNG,
) -> bool:
    """Return True iff ``event`` fires this tick.

    Random events roll ``rng.event(probability_per_tick)``; conditional
    events evaluate their condition callable (which receives ``balance``
    as the second arg).
    """
    if event.trigger_type == "random":
        return rng.event(event.probability_per_tick)
    # conditional
    if event.condition is None:
        # defensive: should not happen if yaml is well-formed
        return False
    return bool(event.condition(state, balance))


# ---------------------------------------------------------------------------
# Effect application.
# ---------------------------------------------------------------------------


def _clamp_market_share(value: float) -> float:
    """Clamp a market_share value to [0.0, 1.0] (Product invariant)."""
    return max(0.0, min(1.0, value))


def _apply_single_effect(
    state: GameState, effect: Effect, balance: dict[str, Any]
) -> GameState:
    """Return a new GameState with one effect applied.

    Pure function: does NOT mutate ``state`` (uses ``dataclasses.replace``
    for fields that change).

    Effects that cannot find their target (e.g. ``ShiftMarketShare`` for a
    missing product) are silently skipped — the engine surfaces them as
    no-ops rather than crashing, so a partially-initialized state still
    survives evaluation.
    """
    if isinstance(effect, ShiftMarketShare):
        pid = effect.product_id
        product = state.products.get(pid)
        if product is None:
            return state
        new_share = _clamp_market_share(product.market_share + effect.delta)
        new_product = dataclasses.replace(product, market_share=new_share)
        return dataclasses.replace(
            state,
            products={**state.products, pid: new_product},
        )

    if isinstance(effect, BoostRevenue):
        pid = effect.product_id
        product = state.products.get(pid)
        if product is None:
            return state
        new_rev = max(0, product.revenue_per_week + effect.amount)
        new_product = dataclasses.replace(product, revenue_per_week=new_rev)
        return dataclasses.replace(
            state,
            products={**state.products, pid: new_product},
        )

    if isinstance(effect, TriggerSecretInvestor):
        # Append a transient marker to state.events_active so the UI / engine
        # can react; we do NOT flip ``secret_investor_cleared`` (that flag
        # is reserved for player resolution, per TriggerSecretInvestor's
        # docstring in domain/event.py).
        marker: dict[str, Any] = {"kind": "trigger_secret_investor"}
        return dataclasses.replace(
            state,
            events_active=[*state.events_active, marker],
        )

    if isinstance(effect, ScheduleEnding):
        from htop_tycoon.domain.ending import EndingType

        # Append to ending_history as a marker; resolution lives in T15.
        marker = {"kind": "schedule_ending", "ending_type": effect.ending_type.value}
        _ = EndingType  # silence unused-import linter; EndingType is referenced for type clarity
        return dataclasses.replace(
            state,
            ending_history=[*state.ending_history, marker],
        )

    if isinstance(effect, AddEmployee):
        # Stub: T10 hire action will own the actual employee generation.
        # For now, just track that the directive was issued.
        marker = {"kind": "add_employee", "dept_id": str(effect.dept_id)}
        return dataclasses.replace(
            state,
            events_active=[*state.events_active, marker],
        )

    if isinstance(effect, RemoveEmployee):
        emp_id = effect.employee_id
        if emp_id not in state.employees:
            return state
        new_employees = {
            eid: emp for eid, emp in state.employees.items() if eid != emp_id
        }
        return dataclasses.replace(state, employees=new_employees)

    if isinstance(effect, ScheduleNextEvent):
        # Chain directive — handled at the queue level by evaluate_events;
        # not applied to state here.
        return state

    # Exhaustiveness: the Effect union has 7 variants; if a new one is added
    # without updating this function, raise loudly at runtime.
    raise ValueError(f"unhandled effect kind: {type(effect).__name__}")


def _apply_effects(
    state: GameState, effects: tuple[Effect, ...], balance: dict[str, Any]
) -> GameState:
    """Apply every effect in order, threading the state through each step."""
    current = state
    for effect in effects:
        current = _apply_single_effect(current, effect, balance)
    return current


# ---------------------------------------------------------------------------
# Public evaluator.
# ---------------------------------------------------------------------------


def evaluate_events(
    state: GameState,
    rng: GameRNG,
    balance: dict[str, Any],
    events_catalog: list[Event],
    active_events: list[EventInstance],
) -> tuple[GameState, list[Event], list[EventInstance]]:
    """Evaluate event triggers for one tick, apply effects, return results.

    Algorithm:

        1. Build ``chain_targets`` = ids of every event that is the target
           of some ``ScheduleNextEvent`` (these are "chain-only" — they
           will NOT fire as catalog triggers, only when reached via chain).
        2. Build the initial queue = carry-over ``active_events`` plus every
           catalog event that is NOT a chain target (added at depth 0).
        3. Process the queue FIFO:
             - Skip events whose trigger does not fire this tick.
             - Otherwise apply effects, append the event to ``fired``.
             - For each ``ScheduleNextEvent`` effect: if the new chain
               depth is < ``max_concurrent_chain_depth``, queue the named
               follow-up event at depth + 1. Otherwise truncate (drop).
        4. Return the final state, the list of fired events, and an empty
           ``active_events`` (chains resolve within this call; no carry-over).

    Args:
        state: Current game state (read-only; never mutated).
        rng: Game RNG for random event rolls.
        balance: Parsed ``balance.yaml`` dict (passed to conditions; not
            otherwise used here).
        events_catalog: Full list of events loaded from yaml.
        active_events: Carry-over chain events from the previous tick.
            Events here are evaluated first.

    Returns:
        ``(new_state, fired_events, new_active_events)``. ``fired_events``
        contains every event that fired this tick in evaluation order.
        ``new_active_events`` is empty when chains resolve within the
        call (the default); it carries through only if a future change
        decides to defer chain follow-ups to the next tick.
    """
    by_id: dict[EventId, Event] = {event.id: event for event in events_catalog}

    # Identify events that are pure chain targets. These MUST NOT fire on
    # their own as catalog triggers; they fire only when reached via chain.
    chain_targets: set[EventId] = set()
    for event in events_catalog:
        for effect in event.effects:
            if isinstance(effect, ScheduleNextEvent):
                chain_targets.add(effect.event_id)

    max_levels = int(balance.get("events", {}).get("max_concurrent_chain_depth", 4))

    fired: list[Event] = []
    fired_ids: set[EventId] = set()
    current_state = state

    # Initial queue: carry-over active_events FIRST, then unclaimed catalog
    # events at depth 0.
    queue: list[EventInstance] = list(active_events)
    for event in events_catalog:
        if event.id not in chain_targets:
            queue.append(EventInstance(event=event, chain_depth=0))

    while queue:
        instance = queue.pop(0)
        # Idempotency: if already fired this tick (e.g. reachable via both
        # catalog and chain), skip the duplicate.
        if instance.event.id in fired_ids:
            continue
        if not _event_triggers(instance.event, current_state, balance, rng):
            continue
        fired.append(instance.event)
        fired_ids.add(instance.event.id)
        current_state = _apply_effects(current_state, instance.event.effects, balance)
        # Schedule chain follow-ups.
        for effect in instance.event.effects:
            if isinstance(effect, ScheduleNextEvent):
                new_depth = instance.chain_depth + 1
                if new_depth < max_levels:
                    target = by_id.get(effect.event_id)
                    if target is not None:
                        queue.append(
                            EventInstance(event=target, chain_depth=new_depth)
                        )
                # else: truncated; the dropped follow-up is silently
                # discarded (NOT re-queued into new_active_events).

    return current_state, fired, []
