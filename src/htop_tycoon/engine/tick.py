"""Engine: TickEngine — advances GameState week/quarter/year deterministically.

Locks the contract from .omo/plans/htop-tycoon.md line 319-328 (Wave 2 patch
corrects the original quarter formula which had a precedence bug):

- The engine holds a ``GameRNG`` instance (created from the constructor seed)
  and a snapshot of ``balance.yaml``. It advances the RNG once per tick
  (``rng.float()``) so subsequent deterministic flows (T10 hire, T12
  products, T13 competitors) share the same RNG stream.
- ``advance(state, n_ticks=1)`` returns a NEW state via ``dataclasses.replace``
  with:
    - ``tick`` incremented by ``n_ticks``
    - ``game_time.week/quarter/year`` advanced using the LOCKED formulas:
      - ``new_week    = ((week - 1 + n_ticks) % 52) + 1``
      - ``new_quarter = (new_week - 1) // 13 + 1``
      - ``new_year    = year + (week - 1 + n_ticks) // 52``
- The input state is NEVER mutated.
- ``advance(state, 0)`` returns the SAME state object (no-op; no replace).
- ``advance(state, n<0)`` raises ``ValueError``.
- ``TickEngine()`` (no seed) raises ``TypeError``; the seed is required.

The engine is purely synchronous. Textual's ``set_interval`` (T16) will call
``TickEngine.advance`` from the App event loop; for now the engine does not
schedule ticks itself.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from htop_tycoon.data import load_balance
from htop_tycoon.domain.state import GameState, GameTime
from htop_tycoon.engine.rng import GameRNG

__all__ = ["TickEngine"]


class TickEngine:
    """Deterministic tick loop: advances GameState week/quarter/year by n_ticks.

    The engine owns its own ``GameRNG`` instance. Each call to ``advance``
    advances the RNG once per tick (``rng.float()``), so per-tick consumers
    that share this engine observe a single deterministic stream.

    Construction requires an integer ``seed`` (``TickEngine()`` raises
    ``TypeError``); the seed also seeds ``state.rng_seed`` upstream via
    ``new_game(seed)`` for persistence reproducibility.
    """

    __slots__ = ("_balance", "_rng")

    def __init__(self, seed: int) -> None:
        """Initialize the engine with a seed.

        Given: an integer ``seed``
        When: ``TickEngine(seed)`` is constructed
        Then: a fresh ``GameRNG(seed)`` is held internally and ``balance.yaml``
              is loaded (and lru-cached by ``data.load_balance``).

        Raises:
            TypeError: if ``seed`` is not an integer (e.g. ``None``, missing).
        """
        # ``isinstance(True, int)`` is True in Python; reject bool explicitly so
        # ``TickEngine(seed=True)`` is treated as a TypeError, not a silent
        # implicit conversion to 1.
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError(
                f"seed must be a strict int, got {type(seed).__name__}: {seed!r}"
            )
        self._rng: GameRNG = GameRNG(seed)
        self._balance: dict[str, Any] = load_balance()

    # ------------------------------------------------------------------ API

    def advance(self, state: GameState, n_ticks: int = 1) -> GameState:
        """Return a new GameState with ``tick`` + ``game_time`` advanced.

        Given: a ``GameState`` and a non-negative ``n_ticks`` count
        When: ``advance(state, n_ticks)`` is called
        Then: a new ``GameState`` is returned with:
              - ``tick`` incremented by ``n_ticks``
              - ``game_time`` recomputed via the LOCKED formulas above
              - all other fields preserved (``dataclasses.replace``)
        And: the RNG is advanced ``n_ticks`` times (``rng.float()`` per tick)

        Special cases:
            - ``n_ticks == 0``: returns the SAME state object (no replace).
            - ``n_ticks < 0``: raises ``ValueError``.

        Raises:
            ValueError: if ``n_ticks`` is negative.
        """
        if n_ticks < 0:
            raise ValueError(f"n_ticks must be >= 0, got {n_ticks!r}")
        if n_ticks == 0:
            return state

        # Advance the RNG once per tick. This consumes randomness that
        # downstream per-tick consumers (T10 hire, T12 products, T13
        # competitors) will pull via ``engine._rng``. Doing it inside
        # advance() guarantees that the same (seed, n_ticks) pair always
        # yields the same RNG state, which is the determinism invariant.
        for _ in range(n_ticks):
            self._rng.float()

        new_game_time = _advance_game_time(state.game_time, n_ticks)
        return dataclasses.replace(
            state,
            tick=state.tick + n_ticks,
            game_time=new_game_time,
        )


# ---------------------------------------------------------------------------
# Pure helper: applies the locked week/quarter/year formulas.
# ---------------------------------------------------------------------------


def _advance_game_time(game_time: GameTime, n_ticks: int) -> GameTime:
    """Return a new ``GameTime`` advanced by ``n_ticks`` using the locked formulas.

    Formulas (per .omo/plans/htop-tycoon.md line 320, Wave 2 patch):

        new_week    = ((week - 1 + n_ticks) % 52) + 1
        new_quarter = (new_week - 1) // 13 + 1     # derived from new_week
        new_year    = year + (week - 1 + n_ticks) // 52

    Quarter mapping (always consistent):
        weeks  1-13 → Q1
        weeks 14-26 → Q2
        weeks 27-39 → Q3
        weeks 40-52 → Q4
    """
    week = game_time.week
    year = game_time.year

    base = week - 1 + n_ticks

    new_week = (base % 52) + 1
    new_quarter = (new_week - 1) // 13 + 1
    new_year = year + base // 52

    return GameTime(year=new_year, quarter=new_quarter, week=new_week)
