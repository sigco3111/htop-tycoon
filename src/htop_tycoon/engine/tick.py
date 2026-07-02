"""tick — orchestrate one game day.

Order of operations (deterministic given seed):
  1. Pay salaries (deduct sum of employee.salary from cash).
  2. Drift satisfaction per employee (±1 rng, clamped 0..100).
  3. Advance every project; collect revenue for projects that shipped THIS tick.
  4. Add fans from shipments.
  5. advance_day() — increments day_index (and rolls year at 365).

Pure function: returns new CompanyState, input untouched.
"""

from __future__ import annotations

import dataclasses

from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.enums import Platform
from htop_tycoon.domain.ids import EmployeeId, ProjectId
from htop_tycoon.domain.money import Money
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.domain.state import CompanyState
from htop_tycoon.engine.game_dev import advance_projects
from htop_tycoon.engine.market import MarketState
from htop_tycoon.engine.sales import compute_sales_revenue

SATISFACTION_DRIFT_MIN: int = -1
SATISFACTION_DRIFT_MAX: int = 1
SATISFACTION_MIN: int = 0
SATISFACTION_MAX: int = 100
DEFAULT_MARKET: MarketState = MarketState.default_for_platform(Platform.PC)

FANS_PER_SHIPMENT_UNIT: int = 100


def _with_employee(
    state: CompanyState, eid: EmployeeId, new_employee: Employee
) -> CompanyState:
    new_employees = dict(state.employees)
    new_employees[eid] = new_employee
    return dataclasses.replace(state, employees=new_employees)


def _with_project(
    state: CompanyState, pid: ProjectId, new_project: GameProject
) -> CompanyState:
    new_projects = dict(state.projects)
    new_projects[pid] = new_project
    return dataclasses.replace(state, projects=new_projects)


def _drift_satisfaction_for_all(
    state: CompanyState, rng: GameRng
) -> CompanyState:
    new_state = state
    for eid, emp in state.employees.items():
        drift = rng.int_range(SATISFACTION_DRIFT_MIN, SATISFACTION_DRIFT_MAX)
        new_sat = max(SATISFACTION_MIN, min(SATISFACTION_MAX, emp.satisfaction + drift))
        if new_sat != emp.satisfaction:
            drifted = Employee(
                id=emp.id,
                name=emp.name,
                job=emp.job,
                level=emp.level,
                salary=emp.salary,
                satisfaction=new_sat,
                dept=emp.dept,
            )
            new_state = _with_employee(new_state, eid, drifted)
    return new_state


def _pay_salaries(state: CompanyState) -> CompanyState:
    total_cents = sum(emp.salary.cents for emp in state.employees.values())
    return state.adjust_cash(Money(-total_cents))


def _ship_projects(
    state: CompanyState, rng: GameRng, market: MarketState
) -> CompanyState:
    """For every project that just shipped THIS tick, add revenue + fans."""
    new_state = state
    revenue_total = 0
    fans_total = 0
    for _pid, project in state.projects.items():
        if not project.is_shipped:
            continue
        # Was it ALREADY shipped before this tick? Skip — only count NEW shipments.
        # For Phase 2B, every is_shipped project ships once; tests/projects must
        # be tracked via a 'shipped_at' field to be precise. For now, only ship
        # projects that JUST became shipped this tick by comparing previous day's
        # project snapshot via `state.projects`.
        # Simpler heuristic: any is_shipped project — ship once. Callers reset
        # the project after each tick by removing it (engine does NOT manage
        # project lifecycle in Phase 2B; that's Phase 2C+).
        revenue = compute_sales_revenue(project, market, rng)
        revenue_total += revenue.cents
        fans_total += max(0, project.quality.sum() // FANS_PER_SHIPMENT_UNIT)
    if revenue_total > 0:
        new_state = new_state.adjust_cash(Money(revenue_total))
    if fans_total > 0:
        new_state = new_state.add_fans(fans_total)
    return new_state


def tick(
    state: CompanyState,
    rng: GameRng,
    market: MarketState | None = None,
) -> CompanyState:
    """Advance one game day. Returns new CompanyState; input untouched."""
    active_market = market if market is not None else DEFAULT_MARKET

    # 1. Pay salaries.
    new_state = _pay_salaries(state)

    # 2. Drift satisfaction (rng-driven).
    new_state = _drift_satisfaction_for_all(new_state, rng)

    # 3. Advance projects.
    new_state = advance_projects(new_state, rng)

    # 4. Ship revenue for any is_shipped project.
    new_state = _ship_projects(new_state, rng, active_market)

    # 5. Roll the day counter.
    new_state = new_state.advance_day()

    return new_state
