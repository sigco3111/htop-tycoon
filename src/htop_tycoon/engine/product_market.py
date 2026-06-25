"""Engine: Product market simulation (T12) — per-tick lifecycle + share dynamics.

Locks the contract from .omo/plans/htop-tycoon.md line 380-389 (T12):

- ``tick_products(state, rng, competitor_actions=None) -> GameState``
  advances each product's lifecycle weeks by 1, recalculates market_share
  based on lifecycle stage + competitor pressure, and refreshes
  ``revenue_per_week`` from the new share + total company skill.
- Lifecycle advance (1 week per tick): delegates to T6's
  ``advance_lifecycle_weeks`` helper.
- Market-share dynamics (locked, sourced from balance.yaml):
    - decline: ``share -= decline_share_loss_per_tick`` (= 0.05), clamped to 0
    - intro:   ``share += intro_share_gain_per_tick`` (= 0.02), capped at
               ``competitor_avg_share`` from ``state.competitors``
    - growth / maturity: ``share`` unchanged (competitor pressure still applies)
- Competitor pressure: each ``CompetitorAction`` with
  ``action_type == "PRICE_CUT"`` shifts PRICE_CUT_STEAL_FRACTION (= 0.02) of
  market_share from the targeted product (``details["target_product"]``) to
  the action's competitor. Both ends are clamped to ``[0.0, 1.0]``. Other
  action types are ignored by this module (their effects live in
  ``competitor_ai`` / events).
- Revenue update:
  ``revenue_per_week = int(market_share * total_company_skill * rpsp)``
  where ``total_company_skill = sum(e.skill for e in state.employees.values())``
  and ``rpsp`` is ``balance["products"]["revenue_per_skill_point_per_week"]``.
- Pure function: input state is NEVER mutated. Output state is a new
  ``GameState`` via ``dataclasses.replace``.
- No event-bus publish call appears in this module; the caller
  dispatches any events. (AGENTS.md invariant: engine returns events;
  the caller dispatches.)

Determinism contract: ``tick_products`` is fully deterministic given
``(state, competitor_actions)``. The ``rng`` parameter is accepted for
forward compatibility with future variance but is currently unused inside
this module.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from htop_tycoon.data import load_balance
from htop_tycoon.domain.product import (
    LifecycleStage,
    Product,
    advance_lifecycle_weeks,
    compute_revenue_per_week,
)
from htop_tycoon.domain.state import (
    CompetitorId,
    GameState,
    ProductId,
)
from htop_tycoon.engine.events import CompetitorAction
from htop_tycoon.engine.rng import GameRNG

__all__ = [
    "ACTION_PRICE_CUT",
    "PRICE_CUT_STEAL_FRACTION",
    "tick_products",
]


# ---------------------------------------------------------------------------
# Locked constants
# ---------------------------------------------------------------------------

# Action type identifier. Mirrors competitor_ai.ACTION_PRICE_CUT. Duplicated
# here (not imported) to keep product_market decoupled from competitor_ai
# (T12 is upstream of T13's full integration; T15's orchestrator will
# join them).
ACTION_PRICE_CUT: str = "PRICE_CUT"

# The fraction of market share transferred per PRICE_CUT. Mirrors
# competitor_ai.PRICE_CUT_STEAL_FRACTION (kept as a local constant so this
# module does not need to import competitor_ai). Changing this is a
# gameplay-tuning decision and must be reflected in balance.yaml.
PRICE_CUT_STEAL_FRACTION: float = 0.02

# Hard bounds for market share. Mirrors product.MARKET_SHARE_* bounds.
SHARE_MIN: float = 0.0
SHARE_MAX: float = 1.0


# ---------------------------------------------------------------------------
# Pure helpers (private to this module)
# ---------------------------------------------------------------------------


def _read_decline_loss(balance: dict[str, Any]) -> float:
    """Read ``balance.products.decline_share_loss_per_tick`` as a float in [0, 1]."""
    value = float(balance["products"]["decline_share_loss_per_tick"])
    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"decline_share_loss_per_tick must be in [0, 1], got {value!r}"
        )
    return value


def _read_intro_gain(balance: dict[str, Any]) -> float:
    """Read ``balance.products.intro_share_gain_per_tick`` as a float in [0, 1]."""
    value = float(balance["products"]["intro_share_gain_per_tick"])
    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"intro_share_gain_per_tick must be in [0, 1], got {value!r}"
        )
    return value


def _read_revenue_per_skill_point(balance: dict[str, Any]) -> int:
    """Read ``balance.products.revenue_per_skill_point_per_week`` as a strict int."""
    raw = balance["products"]["revenue_per_skill_point_per_week"]
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise TypeError(
            "revenue_per_skill_point_per_week must be a strict int, "
            f"got {type(raw).__name__}: {raw!r}"
        )
    return raw


def _competitor_avg_share(state: GameState) -> float:
    """Return the average market_share of all alive competitors in ``state``.

    When no competitors exist, returns 0.0 — interpreted by the intro cap as
    "no cap" (a product in intro is free to grow at +intro_gain_per_tick).
    """
    if not state.competitors:
        return 0.0
    total: float = sum(float(c.market_share) for c in state.competitors.values())
    return total / len(state.competitors)


def _total_company_skill(state: GameState) -> int:
    """Return ``sum(e.skill for e in state.employees.values())``.

    Mirrors the locked formula in the T12 spec.
    """
    return sum(int(emp.skill) for emp in state.employees.values())


def _apply_lifecycle_share_delta(
    product: Product,
    decline_loss: float,
    intro_gain: float,
    cap: float,
) -> Product:
    """Return a new ``Product`` with the per-tick share delta applied.

    Stage rules:
        - decline: ``share -= decline_loss`` (floor at 0.0)
        - intro:   ``share += intro_gain``   (cap at ``cap``; cap <= 0
                   means no cap is applied)
        - growth/maturity: share unchanged
    """
    match product.lifecycle:
        case LifecycleStage.decline:
            new_share = max(SHARE_MIN, product.market_share - decline_loss)
        case LifecycleStage.intro:
            bumped = product.market_share + intro_gain
            # If the cap is 0 or negative, treat it as "no cap" (only happens
            # when state has zero competitors, where there's nothing to
            # compare against).
            if cap <= 0.0:
                new_share = bumped
            else:
                new_share = min(cap, bumped)
        case LifecycleStage.growth | LifecycleStage.maturity:
            new_share = product.market_share
        case _:
            # LifecycleStage is locked at 4 values; unreachable.
            raise AssertionError(
                f"unexpected lifecycle stage: {product.lifecycle!r}"
            )
    if new_share == product.market_share:
        # Avoid an unnecessary dataclasses.replace when nothing changed.
        return product
    return dataclasses.replace(product, market_share=new_share)


def _apply_price_cut(
    products: dict[ProductId, Product],
    competitors: dict[CompetitorId, Any],
    action: CompetitorAction,
) -> tuple[dict[ProductId, Product], dict[CompetitorId, Any]]:
    """Apply one PRICE_CUT action's share shift; return updated dicts.

    Behavior:
        - Look up ``action.details["target_product"]`` (string); cast to
          ``ProductId``.
        - Decrement the target product's market_share by
          ``PRICE_CUT_STEAL_FRACTION`` (clamped at 0.0).
        - Increment the action's competitor's market_share by the same
          amount (clamped at 1.0).
        - Missing / unknown target: silently no-op (the event is still
          surfaced by competitor_ai; tick_products just ignores malformed
          actions defensively).
    """
    if action.action_type != ACTION_PRICE_CUT:
        return products, competitors
    target_raw = action.details.get("target_product")
    if target_raw is None:
        return products, competitors
    target_id = ProductId(str(target_raw))
    if target_id not in products:
        return products, competitors
    if action.competitor_id not in competitors:
        return products, competitors

    target = products[target_id]
    competitor = competitors[action.competitor_id]

    new_product_share = max(SHARE_MIN, target.market_share - PRICE_CUT_STEAL_FRACTION)
    new_competitor_share = min(
        SHARE_MAX, competitor.market_share + PRICE_CUT_STEAL_FRACTION
    )

    new_products = dict(products)
    new_products[target_id] = dataclasses.replace(
        target, market_share=new_product_share
    )
    new_competitors = dict(competitors)
    new_competitors[action.competitor_id] = dataclasses.replace(
        competitor, market_share=new_competitor_share
    )
    return new_products, new_competitors


def _refresh_revenue(
    product: Product,
    total_skill: int,
    revenue_per_skill_point: int,
) -> Product:
    """Return ``product`` with revenue_per_week recomputed from current share."""
    new_rev = compute_revenue_per_week(
        product, total_skill, revenue_per_skill_point
    )
    if new_rev == product.revenue_per_week:
        return product
    return dataclasses.replace(product, revenue_per_week=new_rev)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def tick_products(
    state: GameState,
    rng: GameRNG,  # noqa: ARG001 — reserved for future variance
    competitor_actions: list[CompetitorAction] | None = None,
) -> GameState:
    """Advance every product by one week and refresh share + revenue.

    Given: a ``GameState`` (any shape; empty products is allowed)
    When: ``tick_products(state, rng, competitor_actions)`` is called
    Then: a NEW ``GameState`` is returned with:
        - each product's ``lifecycle`` and ``weeks_in_stage`` advanced by
          one week (via ``advance_lifecycle_weeks``)
        - each product's ``market_share`` adjusted per its lifecycle stage:
            * decline: ``-= decline_share_loss_per_tick``, floored at 0.0
            * intro:   ``+= intro_share_gain_per_tick``, capped at
              ``avg(c.market_share for c in state.competitors.values())``
              (no cap when there are zero competitors)
            * growth/maturity: unchanged
        - each product's ``revenue_per_week`` recomputed as
          ``int(market_share * total_company_skill * rpsp)``
        - each ``PRICE_CUT`` in ``competitor_actions`` shifts
          ``PRICE_CUT_STEAL_FRACTION`` (= 0.02) of ``market_share`` from the
          targeted product (``details["target_product"]``) to the action's
          competitor; both ends clamped to ``[0.0, 1.0]``
    And: the input state is NEVER mutated.

    Args:
        state: The current ``GameState``. Read-only.
        rng: The shared ``GameRNG`` for this tick. Currently unused inside
            this module (reserved for future variance — e.g., stochastic
            price noise). Accepting the parameter keeps the signature
            aligned with other engine modules so the orchestrator can pass
            one RNG to all per-tick consumers.
        competitor_actions: Optional list of ``CompetitorAction`` events
            produced by ``competitor_ai.step_competitors`` this tick. Each
            ``PRICE_CUT`` action applies its share-shift; non-PRICE_CUT
            actions are ignored here.

    Returns:
        A new ``GameState`` (via ``dataclasses.replace``) with the per-tick
        market simulation applied.
    """
    # Empty-state fast path: no products, nothing to tick. We still load
    # balance to validate the keys (so misconfigured balance fails loudly
    # even in degenerate scenarios).
    balance = load_balance()
    decline_loss = _read_decline_loss(balance)
    intro_gain = _read_intro_gain(balance)
    revenue_per_skill_point = _read_revenue_per_skill_point(balance)
    lifecycle_weeks: dict[str, int] = dict(balance["products"]["lifecycle_weeks"])

    if not state.products:
        return state

    cap = _competitor_avg_share(state)
    total_skill = _total_company_skill(state)

    # Phase 1: lifecycle advance + lifecycle-driven share delta + revenue refresh.
    new_products: dict[ProductId, Product] = {}
    for pid, product in state.products.items():
        advanced = advance_lifecycle_weeks(product, 1, lifecycle_weeks)
        advanced = _apply_lifecycle_share_delta(
            advanced, decline_loss, intro_gain, cap
        )
        advanced = _refresh_revenue(advanced, total_skill, revenue_per_skill_point)
        new_products[pid] = advanced

    # Phase 2: competitor pressure (PRICE_CUT) — applied AFTER the lifecycle
    # share deltas so the engine sees the post-lifecycle share as the baseline
    # for any theft.
    new_competitors: dict[CompetitorId, Any] = dict(state.competitors)
    if competitor_actions:
        for action in competitor_actions:
            new_products, new_competitors = _apply_price_cut(
                new_products, new_competitors, action
            )

    # Phase 3: refresh revenue once more so PRICE_CUT's share shift is
    # reflected in revenue_per_week within the same tick. (Plan spec says
    # revenue updates per tick; competitor pressure affects share, which
    # affects revenue, so we re-derive here.)
    final_products: dict[ProductId, Product] = {}
    for pid, product in new_products.items():
        final_products[pid] = _refresh_revenue(
            product, total_skill, revenue_per_skill_point
        )

    return dataclasses.replace(
        state,
        products=final_products,
        competitors=new_competitors,
    )
