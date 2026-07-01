"""htop-tycoon v3.0 — per-day tick driver. Spec §5.2, §5.3.

Pure-function pipeline that advances the simulation by one game-day:

  1. Strategy Manager decides (skipped here — Wave 4)
  2. Execute planned actions (skipped here — manual play only in Wave 3)
  3. Advance in-progress games      (inline stub; real impl lands in game_dev.py)
  4. Market dynamics                (engine.market.tick_market)
  5. End-of-day / award events      (engine.award.* — invoked by UI / cron, not per-day)
  6. Endings check                  (engine.endings.check_endings)

Returns ``(new_state, [events])``. No I/O. No mutation. Deterministic given
the same ``(state, seed)`` per spec §7.3.

Wave 3-D scope:
    Replaced the inline market / endings stubs with real calls into the
    newly-added ``engine.market`` and ``engine.endings`` modules. The
    project-advance stub remains (game_dev.py is Wave 3-B).
"""
from __future__ import annotations

from htop_tycoon.domain import Event, GameState
from htop_tycoon.engine.endings import check_endings
from htop_tycoon.engine.market import tick_market
from htop_tycoon.engine.rng import GameRNG


def _stub_advance_projects(state: GameState) -> tuple[GameState, list[Event]]:
    """Inline stub for ``engine.game_dev.advance_projects``. No-op until W3-B."""
    return state, []


def run_day(state: GameState, rng: GameRNG) -> tuple[GameState, list[Event]]:
    """Advance the simulation by one game-day. Spec §5.2 + §5.3.

    Pure function: same ``(state, seed)`` -> identical sequence per §7.3.
    """
    new_state = state.replace(day=state.day + 1)
    events: list[Event] = []

    # 3. advance in-progress games (stub until game_dev.py lands)
    new_state, proj_events = _stub_advance_projects(new_state)
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
