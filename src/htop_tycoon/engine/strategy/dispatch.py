"""htop-tycoon v3.0 — Action dispatch (PlannedAction -> engine action call).

Spec §3.2: ``Strategy.decide(state, rng) -> list[PlannedAction]`` is
followed by ``engine.actions.X (pure function)`` in the per-day pipeline
(§5.2). This module is the bridge: given a ``PlannedAction`` returned by
a strategy, dispatch to the matching ``engine.actions`` function.

This is deliberately a thin dispatch table (per spec §3.2.1 — actions
are explicit, named, and not auto-mapped). New ``ActionKind`` literals
require a manual entry here, which is what we want for type-safety.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from htop_tycoon.domain import Event, GameState
from htop_tycoon.engine import actions as engine_actions
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.strategy.types import PlannedAction

if TYPE_CHECKING:
    pass


# Spec §6: "Strategy decision infinite loop → capped at
# balance.ai.max_actions_per_day (default 10)". The cap lives at the
# tick.py caller; this dispatcher just executes one action.
#: ``MAX_ACTIONS_PER_DAY`` mirrors ``balance.yaml::ai.max_actions_per_day``.
MAX_ACTIONS_PER_DAY: int = engine_actions.MAX_ACTIONS_PER_DAY


def dispatch_action(
    state: GameState,
    rng: GameRNG,
    action: PlannedAction,
) -> tuple[GameState, list[Event]]:
    """Apply a single ``PlannedAction`` to ``state``.

    Routes by ``action.kind`` to the matching ``engine.actions.*`` function.
    Returns ``(new_state, events)``. Unknown ``kind`` values produce a
    structured failure event but do not raise.
    """
    kind = action.kind
    params = action.params
    target = action.target_id

    if kind == "HIRE":
        return engine_actions.hire(
            state, rng,
            dept=params["dept"],
            job=params["job"],
        )
    if kind == "FIRE":
        return engine_actions.fire(
            state, rng,
            employee_id=target if target is not None else params["employee_id"],
            reason=params.get("reason", "strategy"),
        )
    if kind == "TRAIN":
        return engine_actions.train(
            state, rng,
            employee_id=target if target is not None else params["employee_id"],
            target_level=params["target_level"],
        )
    if kind == "PROMOTE":
        return engine_actions.promote(
            state, rng,
            employee_id=target if target is not None else params["employee_id"],
        )
    if kind == "DEMOTE":
        return engine_actions.demote(
            state, rng,
            employee_id=target if target is not None else params["employee_id"],
        )
    if kind == "CHANGE_JOB":
        return engine_actions.change_job(
            state, rng,
            employee_id=target if target is not None else params["employee_id"],
            new_job=params["new_job"],
        )
    if kind == "START_GAME":
        return engine_actions.start_game(
            state, rng,
            genre_id=params["genre_id"],
            theme_id=params["theme_id"],
            platform_id=params["platform_id"],
        )
    if kind == "ASSIGN":
        return engine_actions.assign(
            state, rng,
            employee_id=target if target is not None else params["employee_id"],
            project_id=target if target is not None else params["project_id"],
        )
    if kind == "NOTHING":
        return engine_actions.nothing(state, rng)

    # Spec §3.2.1 unknown action kind — emit a structured failure event
    # so the UI can show "strategy emitted unknown action" instead of
    # silently dropping the action.
    return state, [Event(
        kind="tick", day=state.day,
        payload={
            "status": "failed",
            "reason": "unknown_action_kind",
            "action_kind": str(kind),
        },
        priority=-50,
    )]


__all__ = ["MAX_ACTIONS_PER_DAY", "dispatch_action"]
