"""Engine: starting-state builder for a "ready to play" new game.

Added in Wave 6 (2026-06-25) so T32 (deterministic playthrough → bankruptcy) and
T33 (5 endings reachable) have a populated starting state to drive. The base
``new_game(seed)`` returns an empty company (no departments/employees/
products/competitors); this module wraps it and populates the default
starting conditions sourced from ``balance.yaml``.

Starting conditions (deterministic given seed):
    - 1 Engineering department, founded_tick=0, unlocked=True
    - 5 employees, all in Engineering, skill in
      ``balance.employees.starting_skill_range`` (default [2, 5]), tier=1,
      salary_per_week=balance.employees.starting_salary_per_week (default 1000),
      satisfaction=70, names from ``korean_names.yaml`` via the shared
      ``GameRNG(seed)`` instance.
    - 1 SaaS product in ``intro`` stage, weeks_in_stage=0, market_share=0.1
    - 3 competitors from ``load_default_market(balance)`` (Incumbents-Co,
      Disruptors-Inc, Foreign-LLC)

Cash flow consequence: with 5 employees at 1000/week each = 5000/week payroll
and 1 product with revenue ~24/week (skill * market_share * 12), the company
burns ~4976/week. Starting cash 50,000, bankruptcy floor -10,000 → bankruptcy
in ~12 weeks. (Actual frozen value will reflect this; the T32 lock-in captures
whatever the balance produces.)
"""

from __future__ import annotations

import dataclasses

from htop_tycoon.data import load_balance
from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.market import load_default_market
from htop_tycoon.domain.product import LifecycleStage, Product, ProductType
from htop_tycoon.domain.state import (
    DepartmentId,
    EmployeeId,
    GameState,
    ProductId,
    new_game,
)
from htop_tycoon.engine.names import generate_korean_name
from htop_tycoon.engine.rng import GameRNG


def new_started_game(seed: int) -> GameState:
    """Build a 'ready to play' GameState with default starting conditions.

    Deterministic given ``seed`` (same seed → identical state, including
    employee names from korean_names.yaml). Uses a single shared
    ``GameRNG(seed)`` for all random draws so reproducibility is end-to-end.

    Args:
        seed: RNG seed (also stored on GameState as ``rng_seed``).

    Returns:
        A fully populated ``GameState`` with:
            - 1 Engineering department (unlocked, founded_tick=0)
            - 5 employees (head + 4) all in Engineering, tier=1, skill in
              balance.employees.starting_skill_range
            - 1 SaaS product in intro stage
            - 3 default competitors
    """
    base = new_game(seed)
    balance = load_balance()
    rng = GameRNG(seed)
    market = load_default_market(balance)

    # 1. Department
    dept_id = DepartmentId("dept-engineering")
    head_emp_id = EmployeeId("emp-1")

    # 2. 5 employees (head + 4)
    employees: dict[EmployeeId, Employee] = {}
    employee_ids: list[EmployeeId] = []
    skill_lo = int(balance["employees"]["starting_skill_range"][0])
    skill_hi = int(balance["employees"]["starting_skill_range"][1])
    salary = int(balance["employees"]["starting_salary_per_week"])

    for i in range(5):
        eid = EmployeeId(f"emp-{i + 1}")
        name = generate_korean_name(rng)
        skill = rng.int(skill_lo, skill_hi)
        employees[eid] = Employee(
            id=eid,
            name=name,
            dept_id=dept_id,
            skill=skill,
            tier=1,
            salary_per_week=salary,
            satisfaction=70,
            hired_tick=0,
        )
        employee_ids.append(eid)

    # 3. 1 SaaS product
    products: dict[ProductId, Product] = {
        ProductId("prod-saas-1"): Product(
            id=ProductId("prod-saas-1"),
            type=ProductType.SaaS,
            lifecycle=LifecycleStage.intro,
            weeks_in_stage=0,
            market_share=0.1,
            revenue_per_week=0,  # recomputed on first tick by T12
        )
    }

    # 4. Departments
    departments: dict[DepartmentId, Department] = {
        dept_id: Department(
            id=dept_id,
            type=DepartmentType.Engineering,
            head_employee_id=head_emp_id,
            employee_ids=employee_ids,
            founded_tick=0,
            unlocked=True,
        )
    }

    # 5. Assemble
    return dataclasses.replace(
        base,
        departments=departments,
        employees=employees,
        products=products,
        competitors=market.competitors,
    )


__all__ = ["new_started_game"]
