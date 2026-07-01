"""htop-tycoon v3.0 — per-day tick driver. Spec §5.2, §5.3.

Pure-function pipeline that advances the simulation by one game-day:

  1. Strategy Manager decides   (engine.strategy.<T>.decide)
  2. Execute planned actions   (engine.strategy.dispatch.dispatch_action)
  3. Advance in-progress games  (engine.game_dev.advance_projects)
  4. Market dynamics            (engine.market.tick_market)
  5. End-of-day / award events  (engine.award.* — invoked by UI / cron, not per-day)
  6. Endings check              (engine.endings.check_endings)

Returns ``(new_state, [events])``. No I/O. No mutation. Deterministic given
the same ``(state, seed)`` per spec §7.3.

Strategy Manager integration (spec §3.3): when ``strategy is None`` the
caller is in manual-play mode (no AI actions). When a ``Strategy``
instance is provided, step 1+2 fire and the AI's planned actions are
applied (capped at ``MAX_ACTIONS_PER_DAY`` per spec §6). The
frozen-hash regression test (Wave 3 partial lock) runs with
``strategy=None`` so the hash stays invariant.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from htop_tycoon.domain import Event, GameState
from htop_tycoon.engine.endings import check_endings
from htop_tycoon.engine.game_dev import advance_projects
from htop_tycoon.engine.market import tick_market
from htop_tycoon.engine.rng import GameRNG

if TYPE_CHECKING:
    from htop_tycoon.engine.strategy.base import Strategy


def run_day(
    state: GameState,
    rng: GameRNG,
    strategy: Strategy | None = None,
) -> tuple[GameState, list[Event]]:
    """Advance the simulation by one game-day. Spec §5.2 + §5.3.

    Pure function: same ``(state, seed)`` -> identical sequence per §7.3.
    Pass ``strategy`` to enable AI auto-play; pass ``None`` (or omit) for
    manual play (the UI dispatches actions directly via ``engine.actions``).
    """
    new_state = state.replace(day=state.day + 1)
    events: list[Event] = []

    # 1+2: Strategy Manager decides + execute (Wave 4 integration).
    if strategy is not None:
        # Imported here (not at module top) to avoid a circular dependency
        # when the strategy package is imported during engine.__init__.
        from htop_tycoon.engine.strategy.dispatch import (
            MAX_ACTIONS_PER_DAY,
            dispatch_action,
        )
        planned = strategy.decide(new_state, rng)
        for action in planned[:MAX_ACTIONS_PER_DAY]:
            new_state, action_events = dispatch_action(new_state, rng, action)
            events.extend(action_events)

    # 3. advance in-progress games (real impl from engine.game_dev)
    new_state, proj_events = advance_projects(new_state)
    events.extend(proj_events)

    # 4. market dynamics (real impl from engine.market)
    new_state, market_events = tick_market(new_state)
    events.extend(market_events)

    # 6. endings check (real impl from engine.endings; priority-ordered per §1.4)
    ending_event = check_endings(new_state)
    if ending_event is not None:
        events.append(ending_event)

    # Daily tick event for UI re-render. Low priority so it sorts last in
    # any UI list and is cheap to ignore when batching.
    events.append(Event(kind="tick", day=new_state.day, priority=-100))

    return new_state, events


__all__ = ["run_day"]
