"""Engine: ending evaluation, apply_ending, story branch resolver (T15).

Locks the contract from .omo/plans/htop-tycoon.md line 415-432:

- ``evaluate_endings`` checks the 5 endings in EXACT priority order
  (BANKRUPTCY > HOSTILE_MA > VOLUNTARY_SALE > IPO > SECRET) and returns
  the FIRST triggered ending (highest priority wins on ties). Returns
  ``None`` when no condition triggers.
- ``apply_ending`` appends a marker to ``state.ending_history`` via
  ``dataclasses.replace`` and returns ``[EndingTriggered(ending_type)]``.
  It does NOT mutate input state and does NOT clear game state (state is
  preserved for the T21 review screen).
- ``resolve_story_branch`` looks up the StoryNode by id from a
  caller-supplied catalog, invokes the chosen option's ``on_choose``
  callback, and returns the (possibly replaced) state.

The priority order is LOCKED. Changing it requires updating this todo,
T8 (the EndingCondition evaluators), and T33 (the secret ending).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from htop_tycoon.domain.ending import (
    BANKRUPTCY,
    HOSTILE_MA,
    IPO,
    SECRET,
    VOLUNTARY_SALE,
    EndingCondition,
    EndingType,
    EvaluationContext,
)
from htop_tycoon.domain.event import StoryNode
from htop_tycoon.domain.state import GameState, StoryNodeId
from htop_tycoon.engine.events import EndingTriggered, Event

__all__ = [
    "PRIORITY_ORDER",
    "apply_ending",
    "evaluate_endings",
    "resolve_story_branch",
]


# ---------------------------------------------------------------------------
# Locked priority order — DO NOT REORDER.
# ---------------------------------------------------------------------------
#
# 1. BANKRUPTCY   — company cash below the bankruptcy floor
# 2. HOSTILE_MA   — an alive competitor with cash >= our market_cap AND high aggression
# 3. VOLUNTARY_SALE — player_action == "sell" AND cash >= voluntary_sale_min_cash
# 4. IPO          — market_cap >= ipo threshold AND cash > 0
# 5. SECRET       — all depts unlocked AND all employees at max_skill AND secret_investor_cleared
#
# Rationale: BANKRUPTCY must fire first because once the company is bankrupt
# nothing else matters. HOSTILE_MA next (forced acquisition trumps player
# intent). VOLUNTARY_SALE only triggers on explicit player action, but if
# the player says "sell" while already hostile-MA-eligible, HOSTILE_MA still
# wins (we do not auto-sell for the player). IPO outranks SECRET because
# going public is the conventional happy path; SECRET is a deliberate
# completionist gate behind it.

PRIORITY_ORDER: tuple[EndingCondition, ...] = (
    BANKRUPTCY,
    HOSTILE_MA,
    VOLUNTARY_SALE,
    IPO,
    SECRET,
)


# ---------------------------------------------------------------------------
# evaluate_endings — priority-ordered dispatcher.
# ---------------------------------------------------------------------------


def evaluate_endings(
    state: GameState,
    balance: dict[str, Any],
    player_action: str | None = None,
) -> EndingType | None:
    """Return the highest-priority ending whose condition fires, or None.

    Iterates ``PRIORITY_ORDER`` and returns the first ``EndingType`` whose
    ``evaluate(state, ctx)`` returns ``True``. When no condition fires,
    returns ``None``.

    Args:
        state: The current ``GameState``. Read-only here (no mutation).
        balance: Parsed ``balance.yaml`` mapping. Accepted for forward
            compatibility with the engine's "thread everything through"
            convention; the underlying evaluators in ``domain.ending`` read
            from ``load_balance()`` themselves today, so ``balance`` is
            not actively consumed.
        player_action: Transient per-tick player intent (e.g. ``"sell"``).
            Defaults to ``None``. Only ``VOLUNTARY_SALE`` reads this; the
            other 4 evaluators ignore it.

    Returns:
        The first triggered ``EndingType`` in priority order, or ``None``
        if no ending condition fires.
    """
    ctx = EvaluationContext(player_action=player_action)
    for condition in PRIORITY_ORDER:
        if condition.evaluate(state, ctx):
            return condition.ending_type
    return None


# ---------------------------------------------------------------------------
# apply_ending — append to ending_history, return EndingTriggered event.
# ---------------------------------------------------------------------------


def apply_ending(
    state: GameState, ending_type: EndingType
) -> tuple[GameState, list[Event]]:
    """Record that ``ending_type`` has triggered and emit a single event.

    Appends a marker dict to ``state.ending_history`` via
    ``dataclasses.replace`` (so the input state is not mutated). Returns
    the new state plus a one-element event list ``[EndingTriggered(...)]``.

    Game state is preserved in full: cash, departments, employees,
    products, competitors, and active events all survive unchanged. The
    T21 EndingScreen widget (review screen) consumes this preserved state
    to render the run summary.

    Args:
        state: Current ``GameState``. Not mutated.
        ending_type: The ``EndingType`` that just triggered.

    Returns:
        ``(new_state, [EndingTriggered(ending_type)])`` — ``new_state``
        has one additional marker in ``ending_history``.
    """
    marker: dict[str, Any] = {
        "kind": "ending_triggered",
        "ending_type": ending_type.value,
    }
    new_state = dataclasses.replace(
        state,
        ending_history=[*state.ending_history, marker],
    )
    return new_state, [EndingTriggered(ending_type)]


# ---------------------------------------------------------------------------
# resolve_story_branch — apply the chosen StoryNode option.
# ---------------------------------------------------------------------------


def resolve_story_branch(
    state: GameState,
    story_node_id: StoryNodeId,
    chosen_option: int,
    story_nodes: dict[StoryNodeId, StoryNode],
) -> GameState:
    """Resolve a player choice on a ``StoryNode`` and return the (possibly replaced) state.

    Looks up ``story_node_id`` in ``story_nodes``; if missing, raises
    ``KeyError`` (fail-loud — no silent no-op). The chosen option's
    ``on_choose`` callback is invoked with the selected ``Choice``. The
    returned state is the input state unchanged (the callback's return
    value is opaque to this dispatcher; engine callers interpret it).

    Args:
        state: Current ``GameState``. Not mutated by this function.
        story_node_id: The id of the StoryNode the player is choosing from.
        chosen_option: Zero-based index into ``node.choices``.
        story_nodes: Caller-supplied mapping of ``StoryNodeId`` to its
            ``StoryNode``. Today the catalog is loaded from
            ``state.events_active`` indirectly (a future mechanism will
            populate this); for now the caller passes it explicitly.

    Returns:
        The input state, unchanged. (Future extensions may thread the
        callback's return value into a ``dataclasses.replace``; today the
        contract is "invoke the callback, return state".)

    Raises:
        KeyError: If ``story_node_id`` is not in ``story_nodes``.
        IndexError: If ``chosen_option`` is out of range for the node's
            ``choices`` tuple.
    """
    node = story_nodes[story_node_id]  # KeyError if missing — intentional.
    choice = node.choices[chosen_option]  # IndexError if out of range.
    node.on_choose(choice)
    return state
