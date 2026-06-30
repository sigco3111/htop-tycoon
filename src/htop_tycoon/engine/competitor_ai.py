"""Engine: Competitor AI (T13) — per-tick action decisions.

Locks the contract from .omo/plans/htop-tycoon.md line 391-403 (T13):

- For each alive competitor, ``rng.float() < competitor.aggression``
  decides whether the competitor takes an action this tick.
- If acting, the competitor picks exactly ONE action per tick from the
  locked distribution:
    - PRICE_CUT         40 %
    - TALENT_POACH      30 %
    - MARKETING_SPREE   30 %
- Action costs come from ``balance.yaml`` under
  ``competitors.action_costs``. No numeric cost is hard-coded in Python.
- Each action returns exactly one ``CompetitorAction`` event in the
  tuple. Pure function: returns ``(new_state, events)``; the input state
  is NEVER mutated and NO ``event_bus.publish`` call is made here (caller
  dispatches).
- ``competitor.cash`` is clamped to 0 (no negative cash, even after
  MARKETING_SPREE deducts the cost).
- TALENT_POACH only targets employees with ``skill > poach_min_skill``
  (strict greater-than). 30% chance to succeed; on success the employee
  is removed AND the player's market_share for the employee's dept's
  primary product drops by 1%.
- MARKETING_SPREE boosts own market_share by 1% and deducts the cost.
  If cash < cost, the action is SKIPPED (no event emitted).
- PRICE_CUT steals 2% market share from a random player product.

AGENTS.md invariants honored here:
- Determinism: every random flow goes through the injected ``GameRNG``;
  no bare ``random.*`` calls.
- State boundary: input state is never mutated; the engine produces a
  new state via ``dataclasses.replace``.
- Event publishing: returns events as data; does not call
  ``event_bus.publish``. The ``tick.py`` orchestrator dispatches them.
- No magic numbers: all tunable costs come from ``balance.yaml``.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from htop_tycoon.data import load_balance
from htop_tycoon.domain.market import Competitor
from htop_tycoon.domain.state import (
    CompetitorId,
    EmployeeId,
    GameState,
    ProductId,
)
from htop_tycoon.engine.competitor_actions import (
    DEPT_PRIMARY_PRODUCT,
    MARKETING_SPREE_BOOST_FRACTION,
    POACH_SUCCESS_PROBABILITY,
    PRICE_CUT_STEAL_FRACTION,
    TALENT_POACH_REDUCE_FRACTION,
    _apply_marketing_spree,
    _apply_price_cut,
    _apply_talent_poach,
)
from htop_tycoon.engine.events import CompetitorAction, Event
from htop_tycoon.engine.regimes import load_regimes_from_balance
from htop_tycoon.engine.rng import GameRNG

__all__ = [
    "ACTION_MARKETING_SPREE",
    "ACTION_PRICE_CUT",
    "ACTION_TALENT_POACH",
    "DEPT_PRIMARY_PRODUCT",
    "MARKETING_SPREE_BOOST_FRACTION",
    "POACH_SUCCESS_PROBABILITY",
    "PRICE_CUT_STEAL_FRACTION",
    "TALENT_POACH_REDUCE_FRACTION",
    "step_competitors",
]


# ---------------------------------------------------------------------------
# Locked action vocabulary (3 actions, sum to 1.0).
# Mirrored in balance.yaml under competitors.action_costs.
# ---------------------------------------------------------------------------

ACTION_PRICE_CUT: str = "PRICE_CUT"
ACTION_TALENT_POACH: str = "TALENT_POACH"
ACTION_MARKETING_SPREE: str = "MARKETING_SPREE"

# Locked probability distribution for action selection (per .omo/plans T13).
# Sum = 1.0; all three are non-negative; the set is the same as the keys
# in balance.yaml[competitors][action_costs].
_ACTION_WEIGHTS: tuple[tuple[str, float], ...] = (
    (ACTION_PRICE_CUT, 0.4),
    (ACTION_TALENT_POACH, 0.3),
    (ACTION_MARKETING_SPREE, 0.3),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def step_competitors(state: GameState, rng: GameRNG) -> tuple[GameState, list[Event]]:
    """Run one tick of competitor AI for every alive competitor in ``state``.

    For each alive competitor, in dict-iteration order:

    1. Roll ``rng.float() < competitor.aggression`` to decide if the
       competitor acts this tick.
    2. If acting, pick exactly one action from the locked distribution
       via ``rng.weighted_choice`` (PRICE_CUT 40 %, TALENT_POACH 30 %,
       MARKETING_SPREE 30 %).
    3. Apply the action's effects to the running competitor / product /
       employee maps.
    4. Append one ``CompetitorAction`` event to the result list.

    Pure function: the input state is NEVER mutated. The engine returns
    ``(new_state, events)`` and the caller (e.g. ``engine.tick``)
    dispatches the events. No ``event_bus.publish`` is called here.

    Args:
        state: The current ``GameState``. Read-only.
        rng: The shared ``GameRNG`` for the tick. Mutated in place
            (advanced by one or two ``float()`` calls per acting
            competitor — see implementation).

    Returns:
        A tuple ``(new_state, events)`` where ``new_state`` is a new
        ``GameState`` with the ``competitors``, ``products``, and
        ``employees`` fields replaced, and ``events`` is the list of
        ``CompetitorAction`` events (one per action taken this tick).
        Dead (``alive=False``) competitors are silently skipped.
    """
    balance = load_balance()
    action_costs: dict[str, int] = _read_action_costs(balance)
    poach_min_skill: int = _read_poach_min_skill(balance)

    # Working copies of the mutable state maps; we will dataclasses.replace
    # at the end. The base state is never mutated.
    new_competitors: dict[CompetitorId, Competitor] = dict(state.competitors)
    new_products: dict[ProductId, Any] = dict(state.products)
    new_employees: dict[EmployeeId, Any] = dict(state.employees)
    events: list[Event] = []

    for comp_id, competitor in state.competitors.items():
        if not competitor.alive:
            # Dead competitors do not act.
            continue
        # T38: aggression threshold is the regime baseline (per
        # balance.yaml regimes.<TYPE>.modifiers.competitor_aggression_baseline)
        # plus the per-competitor aggression. ``baseline`` shifts the
        # baseline macro environment in/out of CRISIS (0.7) without
        # mutating the stored competitor.aggression field.
        cycles = load_regimes_from_balance(load_balance())
        baseline_aggression = cycles[state.regime.current].modifiers.competitor_aggression_baseline
        if not (rng.float() < (baseline_aggression + competitor.aggression)):
            # This tick: no action.
            continue

        # Choose exactly one action. Use weighted_choice to consume the
        # locked distribution with the injected RNG (no bare random.*).
        action_type = _choose_action(rng)

        # Dispatch via match for exhaustive coverage of the locked 3-value
        # vocabulary. Any new action requires a plan update first.
        match action_type:
            case "PRICE_CUT":
                new_products, details = _apply_price_cut(new_products, rng)
            case "TALENT_POACH":
                new_employees, new_products, details = _apply_talent_poach(
                    new_employees, new_products, rng, poach_min_skill
                )
            case "MARKETING_SPREE":
                # Per spec: "If competitor can't afford, skip the action
                # this tick." We interpret "skip" as "the action does not
                # happen" — no event is emitted, no state change. This
                # matches the test contract (no event when cash < cost).
                if competitor.cash < action_costs[ACTION_MARKETING_SPREE]:
                    continue
                new_competitors[comp_id], details = _apply_marketing_spree(
                    competitor, action_costs[ACTION_MARKETING_SPREE]
                )
            case _:
                # Unreachable: action_type is always one of the three
                # locked strings (selected by weighted_choice from
                # _ACTION_WEIGHTS).
                raise AssertionError(f"unreachable action_type: {action_type!r}")

        events.append(
            CompetitorAction(
                competitor_id=comp_id,
                action_type=action_type,
                details=details,
            )
        )

    return (
        dataclasses.replace(
            state,
            competitors=new_competitors,
            products=new_products,
            employees=new_employees,
        ),
        events,
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _read_action_costs(balance: dict[str, Any]) -> dict[str, int]:
    """Read and validate ``balance.competitors.action_costs`` as a dict.

    Each value must be a strict int (or bool-rejecting int-like). The
    three locked action names must all be present.
    """
    raw = balance["competitors"]["action_costs"]
    costs: dict[str, int] = {}
    for name in (ACTION_PRICE_CUT, ACTION_TALENT_POACH, ACTION_MARKETING_SPREE):
        value = raw[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"action_costs[{name!r}] must be a strict int, "
                f"got {type(value).__name__}: {value!r}"
            )
        costs[name] = value
    return costs


def _read_poach_min_skill(balance: dict[str, Any]) -> int:
    """Read ``balance.competitors.poach_min_skill`` as a strict int."""
    value = balance["competitors"]["poach_min_skill"]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"poach_min_skill must be a strict int, got {type(value).__name__}: {value!r}"
        )
    return value


def _choose_action(rng: GameRNG) -> str:
    """Pick one action type from the locked distribution via the RNG."""
    names = [name for name, _ in _ACTION_WEIGHTS]
    weights = [weight for _, weight in _ACTION_WEIGHTS]
    return rng.weighted_choice(names, weights)
