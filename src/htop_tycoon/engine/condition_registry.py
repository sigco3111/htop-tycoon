"""Engine: Condition registry for event triggers (T14).

Locks the contract from .omo/plans/htop-tycoon.md line 406-415:

- A single ``CONDITION_REGISTRY: dict[str, Callable[[GameState, Any], bool]]``
  maps condition names (referenced by ``condition`` strings in
  ``events.yaml``) to pure predicate functions.
- Every condition name referenced in yaml MUST have a matching key here;
  loading yaml without a matching key raises ``ValueError`` at startup
  (fail-loud, no silent skip).
- Conditions are pure ``(state, balance) -> bool``: no mutation, no
  event_bus interaction.
- Numeric thresholds live in ``balance.yaml`` (e.g. ``events.cash_low_threshold``,
  ``events.competitor_aggression_threshold``); the registry reads them at
  call time so balance changes are honored without code edits.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from htop_tycoon.domain.state import GameState

__all__ = [
    "CONDITION_REGISTRY",
    "all_depts_unlocked",
    "all_employees_skill_max",
    "cash_below_threshold",
    "competitor_aggression_high",
    "employee_satisfaction_low",
    "secret_investor_pending",
]


# ---------------------------------------------------------------------------
# Predicate signature.
# ---------------------------------------------------------------------------


# A condition is ``(state, ctx) -> bool`` where ctx is the parsed
# ``balance.yaml`` dict (the same dict passed to ``evaluate_events``).
# Keeping the signature uniform means the registry can be filled with any
# callable matching the shape, including future lambdas / partials.
EventConditionFunc = Callable[[GameState, Any], bool]


# ---------------------------------------------------------------------------
# Concrete conditions.
# ---------------------------------------------------------------------------


def all_depts_unlocked(state: GameState, balance: Any) -> bool:
    """True iff every department in ``state.departments`` has ``unlocked=True``.

    Returns False when there are no departments at all (the SECRET ending
    requires the player to have unlocked all 5).
    """
    if not state.departments:
        return False
    return all(dept.unlocked for dept in state.departments.values())


def all_employees_skill_max(state: GameState, balance: Any) -> bool:
    """True iff every employee's ``skill`` equals ``balance.employees.max_skill``.

    Returns False when there are no employees.
    """
    if not state.employees:
        return False
    max_skill = int(balance["employees"]["max_skill"])
    return all(emp.skill == max_skill for emp in state.employees.values())


def cash_below_threshold(state: GameState, balance: Any) -> bool:
    """True iff ``state.company.cash`` is strictly below the threshold.

    Threshold is sourced from ``balance.events.cash_low_threshold`` with a
    sensible default of 10_000 when the key is missing (e.g. in tests that
    have not injected the balance key).
    """
    threshold = int(
        balance.get("events", {}).get("cash_low_threshold", 10_000)
    )
    return state.company.cash < threshold


def employee_satisfaction_low(state: GameState, balance: Any) -> bool:
    """True iff at least one employee has satisfaction below the threshold.

    Threshold is sourced from ``balance.employees.zombie_satisfaction_threshold``
    (the same value the engine uses to flag zombie employees). When there
    are no employees, the condition is False (no one to be unsatisfied).
    """
    if not state.employees:
        return False
    threshold = int(balance["employees"]["zombie_satisfaction_threshold"])
    return any(
        emp.satisfaction < threshold for emp in state.employees.values()
    )


def secret_investor_pending(state: GameState, balance: Any) -> bool:
    """True iff the secret investor offer has NOT been resolved by the player.

    Reads ``state.secret_investor_cleared``: when False, the offer is still
    pending and conditions that gate on "secret investor not yet cleared"
    are satisfied.
    """
    return not state.secret_investor_cleared


def competitor_aggression_high(state: GameState, balance: Any) -> bool:
    """True iff at least one ALIVE competitor's aggression exceeds the threshold.

    Threshold is sourced from ``balance.events.competitor_aggression_threshold``
    with a sensible default of 0.9 (matches the hostile_ma_trigger from the
    same ``balance.endings`` section). Dead competitors (``alive=False``)
    are ignored.
    """
    threshold = float(
        balance.get("events", {}).get("competitor_aggression_threshold", 0.9)
    )
    return any(
        competitor.aggression > threshold
        for competitor in state.competitors.values()
        if competitor.alive
    )


# ---------------------------------------------------------------------------
# Public registry. Order is alphabetical for readability; lookup is by key.
# ---------------------------------------------------------------------------


CONDITION_REGISTRY: dict[str, EventConditionFunc] = {
    "all_depts_unlocked": all_depts_unlocked,
    "all_employees_skill_max": all_employees_skill_max,
    "cash_below_threshold": cash_below_threshold,
    "competitor_aggression_high": competitor_aggression_high,
    "employee_satisfaction_low": employee_satisfaction_low,
    "secret_investor_pending": secret_investor_pending,
}
