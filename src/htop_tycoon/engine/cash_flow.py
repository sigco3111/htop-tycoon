"""Engine: per-tick cash flow (payroll + revenue).

Added in Wave 6 (2026-06-25) to make T32 (deterministic playthrough → bankruptcy)
achievable. The original plan did not include per-tick cash flow, so player cash
stayed at the starting value and bankruptcy was unreachable. Wave 6 patch
introduces two pure functions:

- ``process_payroll(state, balance)`` — deducts ``sum(emp.salary_per_week for emp in
  state.employees.values())`` from ``state.company.cash``. Returns new state.
- ``process_revenue(state, balance)`` — adds ``sum(p.revenue_per_week for p in
  state.products.values())`` to ``state.company.cash``. Returns new state.

Both functions are PURE (no side effects, no event publishing). The caller
(T16's ``_tick_once``) wires them in this order: revenue first, then payroll
(so a profitable company still pays its employees).

The order is fixed by TDD test: ``test_cash_flow_order_revenue_then_payroll``.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from htop_tycoon.domain.state import GameState


def process_revenue(
    state: GameState, balance: dict[str, Any]
) -> GameState:
    """Deposit the sum of all products' ``revenue_per_week`` into company cash.

    Pure: returns a new GameState via ``dataclasses.replace``; input is
    unchanged. No event publishing.

    Args:
        state: Current game state (read-only).
        balance: Loaded ``balance.yaml`` dict (currently unused but kept for
            symmetry with ``process_payroll`` and future per-product scaling).

    Returns:
        New state with ``company.cash += sum(revenue_per_week)``.
    """
    del balance  # unused for now; reserved for future per-product scaling
    weekly_revenue = sum(
        product.revenue_per_week for product in state.products.values()
    )
    if weekly_revenue == 0:
        return state
    return dataclasses.replace(
        state,
        company=dataclasses.replace(
            state.company, cash=state.company.cash + weekly_revenue
        ),
    )


def process_payroll(
    state: GameState, balance: dict[str, Any]
) -> GameState:
    """Deduct the sum of all employees' ``salary_per_week`` from company cash.

    Pure: returns a new GameState via ``dataclasses.replace``; input is
    unchanged. No event publishing. Cash can go negative (this is how
    bankruptcy accumulates).

    Args:
        state: Current game state (read-only).
        balance: Loaded ``balance.yaml`` dict (currently unused).

    Returns:
        New state with ``company.cash -= sum(salary_per_week)``.
    """
    del balance  # unused for now
    weekly_payroll = sum(
        emp.salary_per_week for emp in state.employees.values()
    )
    if weekly_payroll == 0:
        return state
    return dataclasses.replace(
        state,
        company=dataclasses.replace(
            state.company, cash=state.company.cash - weekly_payroll
        ),
    )


__all__ = ["process_payroll", "process_revenue"]
