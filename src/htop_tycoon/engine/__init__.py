"""Engine package marker for htop-tycoon.

Holds deterministic, side-effect-free game logic: RNG, tick loop, state
transitions, event production. UI must NOT mutate state directly — engine
functions are the only writers.

Re-exports the public surface added by T9:
- ``TickEngine``: deterministic tick loop (1 real-sec = 1 game-week).
- ``EventBus``: one-way Engine->UI event dispatcher.
- Event dataclasses: ``StateUpdated``, ``AlertRaised``, ``EndingTriggered``,
  ``EmployeeHired``, ``EmployeeFired``, ``EmployeePromoted``,
  ``EmployeeDemoted``, ``CompetitorAction``.
"""

from __future__ import annotations

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
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.tick import TickEngine

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
    "GameRNG",
    "StateUpdated",
    "TickEngine",
]
