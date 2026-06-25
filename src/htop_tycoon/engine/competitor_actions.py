"""Engine: per-action handlers for the competitor AI (T13).

These are pure helpers invoked by ``competitor_ai.step_competitors`` for
each of the 3 locked action types:

- ``_apply_price_cut``: steal ``PRICE_CUT_STEAL_FRACTION`` share from a
  random player product.
- ``_apply_talent_poach``: target a random high-skill employee; 30%
  poach chance; on success remove the employee and reduce the player's
  market_share for the employee's dept's primary product.
- ``_apply_marketing_spree``: boost own market_share by
  ``MARKETING_SPREE_BOOST_FRACTION`` and deduct the cost from cash; skip
  when cash < cost (caller must check + not emit an event).

This module is the LEAF in the ``competitor_ai`` import graph: it owns
the per-action fraction constants and the ``DEPT_PRIMARY_PRODUCT``
mapping so that ``competitor_ai`` can import the action handlers
without a circular dependency. ``competitor_ai`` re-exports the
constants and ``DEPT_PRIMARY_PRODUCT`` for public-API consumers.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from htop_tycoon.domain.market import Competitor
from htop_tycoon.domain.state import DepartmentId, EmployeeId, ProductId
from htop_tycoon.engine.rng import GameRNG

# Re-exported by htop_tycoon.engine.competitor_ai for callers that
# prefer the public surface.
DEPT_PRIMARY_PRODUCT: dict[DepartmentId, ProductId] = {
    DepartmentId("Engineering"): ProductId("SaaS"),
    DepartmentId("Sales"): ProductId("SaaS"),
    DepartmentId("Operations"): ProductId("Hardware"),
    DepartmentId("Marketing"): ProductId("Consulting"),
    DepartmentId("Finance"): ProductId("Consulting"),
}

# Per-action tunable fractions (locked from .omo/plans T13).
PRICE_CUT_STEAL_FRACTION: float = 0.02
MARKETING_SPREE_BOOST_FRACTION: float = 0.01
TALENT_POACH_REDUCE_FRACTION: float = 0.01
POACH_SUCCESS_PROBABILITY: float = 0.3

__all__ = [
    "DEPT_PRIMARY_PRODUCT",
    "MARKETING_SPREE_BOOST_FRACTION",
    "POACH_SUCCESS_PROBABILITY",
    "PRICE_CUT_STEAL_FRACTION",
    "TALENT_POACH_REDUCE_FRACTION",
    "_apply_marketing_spree",
    "_apply_price_cut",
    "_apply_talent_poach",
]


def _apply_price_cut(
    products: dict[ProductId, Any],
    rng: GameRNG,
) -> tuple[dict[ProductId, Any], dict[str, Any]]:
    """Steal ``PRICE_CUT_STEAL_FRACTION`` market share from a random product.

    If the player has no products, returns the same dict and flags the
    no-op in ``details`` so the caller (or UI consumer) can detect it.
    """
    if not products:
        return products, {
            "target_product": None,
            "share_stolen": 0.0,
            "skipped": True,
            "reason": "no_player_products",
        }

    target_id = rng.choice(list(products.keys()))
    target = products[target_id]
    new_share = max(0.0, target.market_share - PRICE_CUT_STEAL_FRACTION)
    new_products = dict(products)
    new_products[target_id] = dataclasses.replace(
        target, market_share=new_share
    )
    return new_products, {
        "target_product": str(target_id),
        "share_stolen": PRICE_CUT_STEAL_FRACTION,
    }


def _apply_talent_poach(
    employees: dict[EmployeeId, Any],
    products: dict[ProductId, Any],
    rng: GameRNG,
    poach_min_skill: int,
) -> tuple[
    dict[EmployeeId, Any],
    dict[ProductId, Any],
    dict[str, Any],
]:
    """Target a random ``skill > poach_min_skill`` employee; 30% poach.

    Strict ``>`` (not ``>=``) on ``poach_min_skill``. On success the
    employee is REMOVED and the player's market_share for the dept's
    primary product is reduced by ``TALENT_POACH_REDUCE_FRACTION``
    (floored at 0.0).
    """
    eligible: list[tuple[EmployeeId, Any]] = [
        (eid, emp)
        for eid, emp in employees.items()
        if emp.skill > poach_min_skill
    ]
    if not eligible:
        return employees, products, {
            "target_employee": None,
            "poached": False,
            "primary_product": None,
            "skipped": True,
            "reason": "no_eligible_employees",
        }

    target_id, target_emp = rng.choice(eligible)
    if not (rng.float() < POACH_SUCCESS_PROBABILITY):
        return employees, products, {
            "target_employee": str(target_id),
            "poached": False,
            "primary_product": None,
        }

    new_employees: dict[EmployeeId, Any] = {
        eid: emp for eid, emp in employees.items() if eid != target_id
    }
    new_products = dict(products)
    primary_id: ProductId | None = DEPT_PRIMARY_PRODUCT.get(target_emp.dept_id)
    primary_target: str | None = None
    if primary_id is not None and primary_id in new_products:
        primary = new_products[primary_id]
        new_share = max(
            0.0, primary.market_share - TALENT_POACH_REDUCE_FRACTION
        )
        new_products[primary_id] = dataclasses.replace(
            primary, market_share=new_share
        )
        primary_target = str(primary_id)

    return new_employees, new_products, {
        "target_employee": str(target_id),
        "poached": True,
        "primary_product": primary_target,
    }


def _apply_marketing_spree(
    competitor: Competitor,
    cost: int,
) -> tuple[Competitor, dict[str, Any]]:
    """Boost own ``market_share`` by ``MARKETING_SPREE_BOOST_FRACTION`` and
    deduct ``cost`` from cash. ``caller`` MUST skip the event when this
    function returns the same ``competitor`` instance (signaled by
    ``details["skipped"] == True``).
    """
    if competitor.cash < cost:
        return competitor, {
            "skipped": True,
            "reason": "insufficient_cash",
            "required_cash": cost,
        }

    new_cash = max(0, competitor.cash - cost)
    new_share = min(
        1.0, competitor.market_share + MARKETING_SPREE_BOOST_FRACTION
    )
    new_competitor = dataclasses.replace(
        competitor,
        cash=new_cash,
        market_share=new_share,
    )
    return new_competitor, {
        "cost_paid": cost,
        "share_gained": MARKETING_SPREE_BOOST_FRACTION,
    }
