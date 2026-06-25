"""Engine package marker for htop-tycoon.

Holds deterministic, side-effect-free game logic: RNG, tick loop, state
transitions, event production. UI must NOT mutate state directly — engine
functions are the only writers.

Re-exports the public surface added by T9, T12, T13, T14:
- ``TickEngine``: deterministic tick loop (1 real-sec = 1 game-week).
- ``EventBus``: one-way Engine->UI event dispatcher.
- Event dataclasses: ``StateUpdated``, ``AlertRaised``, ``EndingTriggered``,
  ``EmployeeHired``, ``EmployeeFired``, ``EmployeePromoted``,
  ``EmployeeDemoted``, ``CompetitorAction``.
- ``tick_products``: per-tick product lifecycle + market-share + revenue refresh.
- ``step_competitors``: per-tick competitor AI (aggression -> action roll).
  ``ACTION_PRICE_CUT``, ``ACTION_TALENT_POACH``, ``ACTION_MARKETING_SPREE``:
  the locked 3-value action vocabulary.
- Event chain (T14): ``EventInstance``, ``evaluate_events``,
  ``load_events_catalog``.
- Condition registry (T14): ``CONDITION_REGISTRY`` plus the 6 named
  condition callables.
"""

from __future__ import annotations

from htop_tycoon.engine.competitor_ai import (
    ACTION_MARKETING_SPREE,
    ACTION_PRICE_CUT,
    ACTION_TALENT_POACH,
    step_competitors,
)
from htop_tycoon.engine.condition_registry import (
    CONDITION_REGISTRY,
    all_depts_unlocked,
    all_employees_skill_max,
    cash_below_threshold,
    competitor_aggression_high,
    employee_satisfaction_low,
    secret_investor_pending,
)
from htop_tycoon.engine.event_chain import (
    EventInstance,
    evaluate_events,
    load_events_catalog,
)
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
from htop_tycoon.engine.product_market import tick_products
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.tick import TickEngine

__all__ = [
    "ACTION_MARKETING_SPREE",
    "ACTION_PRICE_CUT",
    "ACTION_TALENT_POACH",
    "AlertRaised",
    "CONDITION_REGISTRY",
    "CompetitorAction",
    "EmployeeDemoted",
    "EmployeeFired",
    "EmployeeHired",
    "EmployeePromoted",
    "EndingTriggered",
    "Event",
    "EventBus",
    "EventInstance",
    "GameRNG",
    "StateUpdated",
    "TickEngine",
    "all_depts_unlocked",
    "all_employees_skill_max",
    "cash_below_threshold",
    "competitor_aggression_high",
    "employee_satisfaction_low",
    "evaluate_events",
    "load_events_catalog",
    "secret_investor_pending",
    "step_competitors",
    "tick_products",
]
