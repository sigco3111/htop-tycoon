"""Engine: Department metrics (CPU/메모리/스왑) derivation from business state.

Locks the contract from .omo/plans/htop-tycoon.md line 364-378 (T11):

- Pure function: ``compute_metrics(state, balance) -> MetricsSnapshot``.
- No event publishing from inside this module (AGENTS.md invariant: "No
  ``event_bus.publish`` calls inside action functions or metrics collectors").
  The caller is responsible for emitting ``MetricsUpdated`` if desired.
- All numeric tunables are read from ``balance.yaml`` via the ``balance`` arg;
  no thresholds or constants are hardcoded.
- Division-by-zero: when ``len(state.departments) == 0``, ``mem_pct`` returns
  ``0`` (sentinel). Rationale: a company with no departments has no
  employees by definition, so 0% memory utilization is the semantically
  correct value. The formula naturally collapses to ``0 / 0`` which would
  raise ``ZeroDivisionError``; we short-circuit before the division.
- The overall ``level`` is the worst of the three per-metric sub-levels
  (``ok < 60``, ``warn < 85``, ``alert >= 85``).

Derivation formulas (locked, must reference balance keys):
    - ``cpu_pct = int(min(100, (cash + sum(revenue_per_week)) / target_revenue * 100))``
    - ``mem_pct = int(total_employees / (n_depts * max_employees_per_dept) * 100)``
    - ``swap_pct = int(max(0, min(100, abs(min(0, cash)) / abs(bankruptcy_cash_floor) * 100)))``
    - ``zombie_count = count(employees with satisfaction < threshold)``
"""

from __future__ import annotations

import dataclasses
from typing import Any, Literal

from htop_tycoon.domain.state import GameState
from htop_tycoon.engine.regimes import load_regimes_from_balance

__all__ = ["LEVEL_ORDER", "MetricsSnapshot", "compute_metrics", "level_for"]

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

# Locked 3-tier severity scale, reused by AlertRaised and the UI footer.
# Order matters: index 0 is least severe ("ok"), index 2 is most ("alert").
LEVEL_ORDER: tuple[Literal["ok"], Literal["warn"], Literal["alert"]] = (
    "ok",
    "warn",
    "alert",
)

# Per-metric level thresholds. The thresholds themselves are *not* game
# balance values (the plan does not require them to be tunable), so they
# live here as locked constants. The plan locks these as ok<60, warn<85,
# alert>=85.
_LEVEL_OK_MAX_EXCLUSIVE: int = 60
_LEVEL_WARN_MAX_EXCLUSIVE: int = 85


@dataclasses.dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Snapshot of htop-style business metrics for one GameState.

    All percentage fields are clamped to ``[0, 100]`` as ints (no floats leak
    to the UI). The overall ``level`` is the worst of the three per-metric
    sub-levels (cpu / mem / swap). ``zombie_count`` is the number of
    employees whose satisfaction is below the zombie threshold from
    ``balance.yaml``.

    Attributes:
        cpu_pct: Revenue/load metric in [0, 100]. Maps to the htop CPU bar.
        mem_pct: Employee-vs-capacity metric in [0, 100]. Maps to htop MEM.
        swap_pct: Debt-vs-bankruptcy metric in [0, 100]. Maps to htop SWAP.
        zombie_count: Number of employees at quitting risk.
        level: Worst-case severity across cpu/mem/swap. One of "ok", "warn",
            "alert".
    """

    cpu_pct: int
    mem_pct: int
    swap_pct: int
    zombie_count: int
    level: Literal["ok", "warn", "alert"]


# ---------------------------------------------------------------------------
# Pure derivation helpers
# ---------------------------------------------------------------------------


def level_for(pct: int) -> Literal["ok", "warn", "alert"]:
    """Return the severity level for a metric value ``pct`` in [0, 100].

    Thresholds (locked): ``ok`` if ``pct < 60``, ``warn`` if ``60 <= pct < 85``,
    ``alert`` if ``pct >= 85``.
    """
    if pct < _LEVEL_OK_MAX_EXCLUSIVE:
        return "ok"
    if pct < _LEVEL_WARN_MAX_EXCLUSIVE:
        return "warn"
    return "alert"


def _worst_level(levels: list[Literal["ok", "warn", "alert"]]) -> Literal["ok", "warn", "alert"]:
    """Return the worst (highest-severity) level from ``levels``."""
    # LEVEL_ORDER is ordered ok -> warn -> alert, so the max index is the
    # worst. Empty input defaults to "ok" (the safe no-alert default).
    worst_idx = 0
    for level in levels:
        idx = LEVEL_ORDER.index(level)
        if idx > worst_idx:
            worst_idx = idx
    return LEVEL_ORDER[worst_idx]


def _compute_cpu_pct(state: GameState, balance: dict[str, Any]) -> int:
    """cpu_pct = int(min(100, (cash + scale * sum_revenue) / target_revenue * 100)).

    T38: only the FLOW (sum of revenue_per_week) is regime-scaled;
    company.cash is a stock and remains as-is. ``NORMAL`` modifier=1.0
    preserves the pre-T38 baseline; ``BOOM``/``CRISIS`` tilt the metric
    by their ``revenue_multiplier``.
    """
    target = float(balance["money"]["target_revenue"])
    cycles = load_regimes_from_balance(balance)
    revenue_multiplier = cycles[state.regime.current].modifiers.revenue_multiplier
    revenue_flow = sum(product.revenue_per_week for product in state.products.values())
    total = state.company.cash + revenue_flow * revenue_multiplier
    return int(min(100, total / target * 100))


def _compute_mem_pct(state: GameState, balance: dict[str, Any]) -> int:
    """mem_pct = int(total_employees / (n_depts * max_per_dept) * 100).

    Division-by-zero guard: when ``len(state.departments) == 0`` returns
    ``0`` (sentinel). See module docstring for rationale.
    """
    n_depts = len(state.departments)
    if n_depts == 0:
        return 0
    max_per_dept = int(balance["departments"]["max_employees_per_dept"])
    total_employees = sum(len(d.employee_ids) for d in state.departments.values())
    return int(total_employees / (n_depts * max_per_dept) * 100)


def _compute_swap_pct(state: GameState, balance: dict[str, Any]) -> int:
    """swap_pct = int(max(0, min(100, abs(min(0, cash)) / abs(floor) * 100)))."""
    floor = abs(float(balance["money"]["bankruptcy_cash_floor"]))
    debt = abs(min(0, state.company.cash))
    return int(max(0, min(100, debt / floor * 100)))


def _compute_zombie_count(state: GameState, balance: dict[str, Any]) -> int:
    """zombie_count = employees with satisfaction < threshold."""
    threshold = int(balance["employees"]["zombie_satisfaction_threshold"])
    return sum(1 for e in state.employees.values() if e.satisfaction < threshold)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_metrics(state: GameState, balance: dict[str, Any]) -> MetricsSnapshot:
    """Return a ``MetricsSnapshot`` derived from ``state`` and ``balance``.

    Pure function. Does NOT publish events; the caller is responsible for
    emitting a ``MetricsUpdated`` event if the UI needs to be notified.

    Args:
        state: The current ``GameState``. Not mutated.
        balance: The parsed ``balance.yaml`` mapping (typically from
            ``htop_tycoon.data.load_balance()``).

    Returns:
        A frozen ``MetricsSnapshot`` with cpu/mem/swap percentages, the
        zombie employee count, and the overall severity level.
    """
    cpu_pct = _compute_cpu_pct(state, balance)
    mem_pct = _compute_mem_pct(state, balance)
    swap_pct = _compute_swap_pct(state, balance)
    zombie_count = _compute_zombie_count(state, balance)
    level = _worst_level([level_for(cpu_pct), level_for(mem_pct), level_for(swap_pct)])
    return MetricsSnapshot(
        cpu_pct=cpu_pct,
        mem_pct=mem_pct,
        swap_pct=swap_pct,
        zombie_count=zombie_count,
        level=level,
    )
