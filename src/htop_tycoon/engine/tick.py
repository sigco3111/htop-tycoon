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
from htop_tycoon.engine.endings import (
    MEGA_HIT_UNITS,
    detect_ending,
    record_ending,
)
from htop_tycoon.engine.game_dev import advance_projects
from htop_tycoon.engine.market import MarketState
from htop_tycoon.engine.sales import compute_sales_revenue, compute_units_sold

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
    """For every project that just shipped THIS tick, add revenue + fans.

    Detects "just shipped" projects via units_sold == 0 (only newly-shipped
    projects have units_sold=0; shipped-this-tick projects get their units
    computed fresh, then their counters bumped). Pre-shipped projects
    (units_sold > 0) keep their final counters.
    """
    new_state = state
    revenue_total = 0
    fans_total = 0
    shipped_ids: list[ProjectId] = []
    for pid, project in state.projects.items():
        if not project.is_shipped:
            continue
        if project.units_sold > 0:
            continue
        units = compute_units_sold(project, market, rng)
        revenue = compute_sales_revenue(project, market, rng)
        revenue_total += revenue.cents
        fans_total += max(0, project.quality.sum() // FANS_PER_SHIPMENT_UNIT)
        new_project = dataclasses.replace(project, units_sold=units)
        new_state = _with_project(new_state, pid, new_project)
        shipped_ids.append(pid)
    if revenue_total > 0:
        new_state = new_state.adjust_cash(Money(revenue_total))
    if fans_total > 0:
        new_state = new_state.add_fans(fans_total)
    for pid in shipped_ids:
        new_state = new_state.increment_games_shipped()
        if new_state.projects[pid].units_sold >= MEGA_HIT_UNITS:
            new_state = new_state.increment_mega_hits()
    return new_state


def _update_counters_and_legacy(state: CompanyState) -> CompanyState:
    """Recount games_shipped + mega_hits from projects (idempotent re-derivation).

    Used to handle pre-shipped projects (units_sold > 0) that need counters
    bumped without re-running revenue calc.
    """
    games_shipped = sum(1 for p in state.projects.values() if p.units_sold > 0)
    mega_hits = sum(1 for p in state.projects.values() if p.units_sold >= MEGA_HIT_UNITS)
    new_state = dataclasses.replace(
        state, games_shipped=games_shipped, mega_hits=mega_hits
    )
    return new_state


def _record_legacy_after_tick(state: CompanyState) -> CompanyState:
    ending = detect_ending(state)
    if ending is None:
        return state
    return record_ending(state, ending)


def tick(
    state: CompanyState,
    rng: GameRng,
    market: MarketState | None = None,
) -> CompanyState:
    """Advance one game day. Returns new CompanyState; input untouched."""
    active_market = market if market is not None else DEFAULT_MARKET

    new_state = _pay_salaries(state)
    new_state = _drift_satisfaction_for_all(new_state, rng)
    new_state = advance_projects(new_state, rng)
    new_state = _ship_projects(new_state, rng, active_market)
    new_state = _update_counters_and_legacy(new_state)
    new_state = _record_legacy_after_tick(new_state)
    new_state = new_state.advance_day()

    return new_state
