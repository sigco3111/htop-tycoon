"""Tests for T12: engine.product_market (tick_products simulation).

Locks the contract from .omo/plans/htop-tycoon.md line 380-389 (T12):

- ``tick_products(state, rng, competitor_actions=None) -> GameState`` advances
  each product's lifecycle by 1 week, recalculates market_share based on the
  locked lifecycle dynamics, applies PRICE_CUT competitor pressure, and
  refreshes revenue_per_week from the new market_share + total_company_skill.
- Lifecycle dynamics (locked, sourced from balance.yaml):
    - decline: market_share -= decline_share_loss_per_tick (0.05), clamped to 0
    - intro:   market_share += intro_share_gain_per_tick   (0.02),
               capped at competitor_avg_share from state.competitors
    - growth/maturity: market_share unchanged (competitor pressure still applies)
- Competitor pressure: each PRICE_CUT entry in ``competitor_actions`` shifts
  ``PRICE_CUT_STEAL_FRACTION`` (= 0.02) of market_share from the targeted
  product (details["target_product"]) to the action's competitor
  (``action.competitor_id``). Both ends are clamped to [0.0, 1.0].
- Revenue: ``revenue_per_week = int(market_share * total_skill * rpsp)``,
  where ``total_skill = sum(e.skill for e in state.employees.values())``
  and ``rpsp`` is ``balance["products"]["revenue_per_skill_point_per_week"]``.
- Pure function: the input state is NEVER mutated.
- No ``event_bus.publish(...)`` call appears in ``product_market.py``.
- Determinism: same seed + same inputs → same state_hash, every run.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.market import load_default_market
from htop_tycoon.domain.product import (
    LifecycleStage,
    Product,
    ProductType,
)
from htop_tycoon.domain.state import (
    CompetitorId,
    DepartmentId,
    EmployeeId,
    GameState,
    ProductId,
    new_game,
    state_hash,
)
from htop_tycoon.engine.events import CompetitorAction

# Production module under test (imported at module level so pytest collection
# surfaces any ImportError as a red-phase signal if the module is missing).
from htop_tycoon.engine.product_market import tick_products  # noqa: E402
from htop_tycoon.engine.rng import GameRNG

# Frozen expected SHA-256 hex digest of state_hash(tick_products(default_state, GameRNG(42))).
# Captured AFTER the engine was implemented and verified stable across multiple
# consecutive runs on Python 3.12.10 / macOS aarch64. Locking this value
# guarantees that any change to share dynamics, lifecycle interaction, revenue
# formula, or GameState field-set is caught by the determinism invariant test.
# Setup: seed=42, 4 employees (skill=10 each, total=40), 1 SaaS product in
# intro at weeks=0/share=0.05, default 3 competitors from load_default_market.
FROZEN_HASH_AFTER_1_TICK_SEED_42 = (
    "2e7ab7db4f56f5105f58d8baae351a88d62880a66f00fe110b8c367de691adf7"
)

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

# Locked tunable names surfaced from balance.yaml. Per the spec, the per-tick
# share deltas (0.05 / 0.02) MUST live in balance.yaml — not be hardcoded.
PRODUCT_DECLINE_LOSS_KEY = "decline_share_loss_per_tick"
PRODUCT_INTRO_GAIN_KEY = "intro_share_gain_per_tick"
PRICE_CUT_STEAL = 0.02  # competitor_ai.PRICE_CUT_STEAL_FRACTION; documented here.


def _make_employee(emp_id: str, skill: int, *, hired_tick: int = 0) -> Employee:
    """Build a minimal Employee for revenue calculations."""
    return Employee(
        id=EmployeeId(emp_id),
        name=f"Employee {emp_id}",
        dept_id=DepartmentId("Engineering"),
        skill=skill,
        tier=3,
        salary_per_week=1000,
        satisfaction=80,
        hired_tick=hired_tick,
    )


def _make_product(
    *,
    product_id: str = "prod-saas-1",
    lifecycle: LifecycleStage = LifecycleStage.intro,
    weeks_in_stage: int = 0,
    market_share: float = 0.05,
    revenue_per_week: int = 0,
    product_type: ProductType = ProductType.SaaS,
) -> Product:
    """Build a minimal Product for share/revenue tests."""
    return Product(
        id=ProductId(product_id),
        type=product_type,
        lifecycle=lifecycle,
        weeks_in_stage=weeks_in_stage,
        market_share=market_share,
        revenue_per_week=revenue_per_week,
    )


def _make_state(
    *,
    employees: dict[EmployeeId, Employee] | None = None,
    products: dict[ProductId, Product] | None = None,
    competitors: dict[CompetitorId, object] | None = None,
    seed: int = 42,
) -> GameState:
    """Build a GameState with the given maps and default everything else.

    Defaults: 4 employees (skill=10 each, total=40); 1 SaaS product in intro
    with market_share=0.05; default 3 competitors from load_default_market.
    """
    base = new_game(seed)
    if competitors is None:
        competitors = dict(load_default_market(load_balance()).competitors)
    if products is None:
        products = {ProductId("prod-saas-1"): _make_product()}
    if employees is None:
        employees = {
            EmployeeId(f"emp-{i:03d}"): _make_employee(f"emp-{i:03d}", skill=10)
            for i in range(4)
        }
    return dataclasses.replace(
        base,
        employees=employees,
        products=products,
        competitors=competitors,
    )


def _competitor_avg_share(state: GameState) -> float:
    """Compute competitor average share from state (used to verify the cap)."""
    if not state.competitors:
        return 0.0
    return sum(c.market_share for c in state.competitors.values()) / len(
        state.competitors
    )


# ---------------------------------------------------------------------------
# Module surface: balance.yaml has the locked per-tick share deltas.
# ---------------------------------------------------------------------------


class TestProductMarketBalanceYamlContract:
    """The per-tick share deltas live in balance.yaml, not in Python code."""

    def test_decline_share_loss_per_tick_present(self) -> None:
        """balance.yaml exposes products.decline_share_loss_per_tick (= 0.05)."""
        products = load_balance()["products"]
        assert PRODUCT_DECLINE_LOSS_KEY in products, (
            f"balance.yaml must expose products.{PRODUCT_DECLINE_LOSS_KEY}; "
            f"AGENTS.md forbids hardcoded 5% / 2% constants"
        )
        assert float(products[PRODUCT_DECLINE_LOSS_KEY]) == pytest.approx(0.05)

    def test_intro_share_gain_per_tick_present(self) -> None:
        """balance.yaml exposes products.intro_share_gain_per_tick (= 0.02)."""
        products = load_balance()["products"]
        assert PRODUCT_INTRO_GAIN_KEY in products
        assert float(products[PRODUCT_INTRO_GAIN_KEY]) == pytest.approx(0.02)


# ---------------------------------------------------------------------------
# Lifecycle advance (1 week per tick)
# ---------------------------------------------------------------------------


class TestTickProductsLifecycleAdvance:
    """tick_products advances each product's lifecycle by 1 week."""

    def test_intro_weeks_in_stage_increments_by_one(self) -> None:
        """Given: a product in intro with weeks_in_stage=0
        When: tick_products(state, rng) is called
        Then: product.lifecycle still intro, weeks_in_stage == 1
        """
        state = _make_state()
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.lifecycle == LifecycleStage.intro
        assert prod.weeks_in_stage == 1

    def test_intro_with_weeks_in_stage_8_advances_to_growth(self) -> None:
        """Given: a product at intro/weeks=8 (the intro->growth boundary)
        When: tick_products(state, rng) advances by 1 week
        Then: lifecycle advances to growth, weeks_in_stage == 1
        """
        product = _make_product(weeks_in_stage=8)
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.lifecycle == LifecycleStage.growth
        assert prod.weeks_in_stage == 1

    def test_growth_lifecycle_advances_normally(self) -> None:
        """Given: a product in growth at weeks=10
        When: tick_products(state, rng)
        Then: lifecycle still growth, weeks_in_stage == 11
        """
        product = _make_product(
            lifecycle=LifecycleStage.growth, weeks_in_stage=10
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.lifecycle == LifecycleStage.growth
        assert prod.weeks_in_stage == 11

    def test_maturity_lifecycle_advances_normally(self) -> None:
        """Given: a product in maturity at weeks=20
        When: tick_products(state, rng)
        Then: lifecycle still maturity, weeks_in_stage == 21
        """
        product = _make_product(
            lifecycle=LifecycleStage.maturity, weeks_in_stage=20
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.lifecycle == LifecycleStage.maturity
        assert prod.weeks_in_stage == 21


# ---------------------------------------------------------------------------
# Market-share dynamics per lifecycle stage
# ---------------------------------------------------------------------------


class TestTickProductsDeclineShareLoss:
    """Products in decline lose decline_share_loss_per_tick each tick (clamp at 0)."""

    def test_decline_loses_five_percent_per_tick(self) -> None:
        """Given: a decline product with share=0.50
        When: tick_products(state, rng)
        Then: share == 0.45 (0.50 - 0.05)
        """
        product = _make_product(
            lifecycle=LifecycleStage.decline,
            weeks_in_stage=5,
            market_share=0.50,
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.market_share == pytest.approx(0.45)

    def test_decline_share_clamps_at_zero(self) -> None:
        """Given: a decline product with share=0.03 (would go negative)
        When: tick_products(state, rng)
        Then: share == 0.0 (clamped; never negative)
        """
        product = _make_product(
            lifecycle=LifecycleStage.decline,
            weeks_in_stage=5,
            market_share=0.03,
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.market_share == 0.0

    def test_decline_share_stays_at_zero_when_already_zero(self) -> None:
        """Given: a decline product with share=0.0
        When: tick_products(state, rng)
        Then: share stays 0.0
        """
        product = _make_product(
            lifecycle=LifecycleStage.decline,
            weeks_in_stage=5,
            market_share=0.0,
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.market_share == 0.0


class TestTickProductsIntroShareGain:
    """Products in intro gain intro_share_gain_per_tick, capped at competitor avg."""

    def test_intro_gains_two_percent_when_below_cap(self) -> None:
        """Given: intro product at share=0.05, default competitors avg=0.1833...
        When: tick_products(state, rng)
        Then: share == 0.07 (0.05 + 0.02, below the cap)
        """
        product = _make_product(
            lifecycle=LifecycleStage.intro,
            weeks_in_stage=0,
            market_share=0.05,
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.market_share == pytest.approx(0.07)

    def test_intro_share_capped_at_competitor_avg(self) -> None:
        """Given: intro product at share=0.20, default avg=~0.1833
        When: tick_products(state, rng)
        Then: share == competitor_avg (cap; 0.20 + 0.02 would exceed)
        """
        product = _make_product(
            lifecycle=LifecycleStage.intro,
            weeks_in_stage=0,
            market_share=0.20,
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        expected_cap = _competitor_avg_share(state)
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.market_share == pytest.approx(expected_cap)

    def test_intro_cap_with_high_competitor_avg(self) -> None:
        """A custom competitor set with avg=0.50 caps intro growth at 0.50."""
        from htop_tycoon.domain.market import Competitor

        # Three competitors with shares 0.50, 0.50, 0.50 -> avg 0.50.
        competitors = {
            CompetitorId("A"): Competitor(
                id=CompetitorId("A"),
                name="A",
                market_share=0.50,
                aggression=0.5,
                cash=1000,
            ),
            CompetitorId("B"): Competitor(
                id=CompetitorId("B"),
                name="B",
                market_share=0.50,
                aggression=0.5,
                cash=1000,
            ),
            CompetitorId("C"): Competitor(
                id=CompetitorId("C"),
                name="C",
                market_share=0.50,
                aggression=0.5,
                cash=1000,
            ),
        }
        product = _make_product(
            lifecycle=LifecycleStage.intro, market_share=0.49
        )
        state = _make_state(
            products={ProductId("prod-saas-1"): product},
            competitors=competitors,
        )
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.market_share == pytest.approx(0.50)


class TestTickProductsGrowthMaturityStable:
    """Products in growth/maturity have stable share (no automatic change)."""

    def test_growth_share_unchanged_without_competitor_pressure(self) -> None:
        """Given: a growth product at share=0.30, no competitor_actions
        When: tick_products(state, rng)
        Then: share stays 0.30
        """
        product = _make_product(
            lifecycle=LifecycleStage.growth,
            weeks_in_stage=10,
            market_share=0.30,
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.market_share == pytest.approx(0.30)

    def test_maturity_share_unchanged_without_competitor_pressure(self) -> None:
        """Given: a maturity product at share=0.40, no competitor_actions
        When: tick_products(state, rng)
        Then: share stays 0.40
        """
        product = _make_product(
            lifecycle=LifecycleStage.maturity,
            weeks_in_stage=10,
            market_share=0.40,
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.market_share == pytest.approx(0.40)


# ---------------------------------------------------------------------------
# Competitor pressure (PRICE_CUT)
# ---------------------------------------------------------------------------


class TestTickProductsCompetitorPressure:
    """PRICE_CUT actions shift 2% share from the targeted product to the competitor."""

    def test_price_cut_transfers_share_from_target_to_competitor(self) -> None:
        """Given: maturity product at share=0.50, Incumbents-Co competitor at share=0.30
        When: tick_products with PRICE_CUT targeting that product
        Then: product share == 0.48 (loses 2%), competitor share == 0.32 (gains 2%)
        """
        product = _make_product(
            lifecycle=LifecycleStage.maturity,
            weeks_in_stage=10,
            market_share=0.50,
        )
        market = load_default_market(load_balance())
        competitor_id = CompetitorId("Incumbents-Co")
        competitors = dict(market.competitors)
        state = _make_state(
            products={ProductId("prod-saas-1"): product},
            competitors=competitors,
        )
        action = CompetitorAction(
            competitor_id=competitor_id,
            action_type="PRICE_CUT",
            details={
                "target_product": "prod-saas-1",
                "share_stolen": PRICE_CUT_STEAL,
            },
        )
        result = tick_products(state, GameRNG(42), [action])
        prod = result.products[ProductId("prod-saas-1")]
        comp = result.competitors[competitor_id]
        assert prod.market_share == pytest.approx(0.48)
        assert comp.market_share == pytest.approx(0.32)

    def test_price_cut_does_not_affect_other_products(self) -> None:
        """Only the targeted product loses share; other products are unchanged."""
        target = _make_product(
            product_id="prod-target",
            lifecycle=LifecycleStage.maturity,
            weeks_in_stage=5,
            market_share=0.50,
        )
        bystander = _make_product(
            product_id="prod-bystander",
            lifecycle=LifecycleStage.maturity,
            weeks_in_stage=5,
            market_share=0.30,
        )
        market = load_default_market(load_balance())
        competitor_id = CompetitorId("Disruptors-Inc")
        state = _make_state(
            products={
                ProductId("prod-target"): target,
                ProductId("prod-bystander"): bystander,
            },
            competitors=dict(market.competitors),
        )
        action = CompetitorAction(
            competitor_id=competitor_id,
            action_type="PRICE_CUT",
            details={
                "target_product": "prod-target",
                "share_stolen": PRICE_CUT_STEAL,
            },
        )
        result = tick_products(state, GameRNG(42), [action])
        assert result.products[ProductId("prod-bystander")].market_share == pytest.approx(
            0.30
        )

    def test_no_competitor_actions_means_no_competitor_share_change(self) -> None:
        """Given: state with competitors, no competitor_actions
        When: tick_products(state, rng) (default competitor_actions=None)
        Then: every competitor's market_share is unchanged
        """
        state = _make_state()
        before = {cid: c.market_share for cid, c in state.competitors.items()}
        result = tick_products(state, GameRNG(42))
        for cid, share in before.items():
            assert result.competitors[cid].market_share == pytest.approx(share)

    def test_price_cut_clamps_target_at_zero(self) -> None:
        """If the target's share < PRICE_CUT_STEAL_FRACTION, clamp at 0."""
        product = _make_product(
            lifecycle=LifecycleStage.maturity,
            weeks_in_stage=5,
            market_share=0.01,
        )
        market = load_default_market(load_balance())
        competitor_id = CompetitorId("Incumbents-Co")
        state = _make_state(
            products={ProductId("prod-saas-1"): product},
            competitors=dict(market.competitors),
        )
        action = CompetitorAction(
            competitor_id=competitor_id,
            action_type="PRICE_CUT",
            details={
                "target_product": "prod-saas-1",
                "share_stolen": PRICE_CUT_STEAL,
            },
        )
        result = tick_products(state, GameRNG(42), [action])
        assert result.products[ProductId("prod-saas-1")].market_share == 0.0

    def test_price_cut_clamps_competitor_at_one(self) -> None:
        """If the competitor's share would exceed 1.0, clamp at 1.0."""
        from htop_tycoon.domain.market import Competitor

        # Competitor at 0.99; receiving +0.02 would be 1.01 — clamp at 1.0.
        competitors = {
            CompetitorId("big"): Competitor(
                id=CompetitorId("big"),
                name="Big",
                market_share=0.99,
                aggression=0.5,
                cash=1000,
            ),
        }
        product = _make_product(
            lifecycle=LifecycleStage.maturity,
            weeks_in_stage=5,
            market_share=0.50,
        )
        state = _make_state(
            products={ProductId("prod-saas-1"): product},
            competitors=competitors,
        )
        action = CompetitorAction(
            competitor_id=CompetitorId("big"),
            action_type="PRICE_CUT",
            details={
                "target_product": "prod-saas-1",
                "share_stolen": PRICE_CUT_STEAL,
            },
        )
        result = tick_products(state, GameRNG(42), [action])
        assert result.competitors[CompetitorId("big")].market_share == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Revenue update
# ---------------------------------------------------------------------------


class TestTickProductsRevenueUpdate:
    """revenue_per_week is recomputed from the new market_share each tick."""

    def test_revenue_updates_from_new_intro_share(self) -> None:
        """Given: intro product at 0.05, total_skill=40
        When: tick_products (intro gains 2% -> 0.07)
        Then: revenue_per_week == int(0.07 * 40 * 12) == 33
        """
        product = _make_product(
            lifecycle=LifecycleStage.intro, market_share=0.05
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        # int(0.07 * 40 * 12) = int(33.6) = 33
        assert prod.revenue_per_week == 33

    def test_revenue_uses_total_company_skill(self) -> None:
        """Given: a product with share=0.10, 4 employees with skill=5 each (total=20)
        When: tick_products
        Then: revenue_per_week == int(0.10 * 20 * 12) == 24
        """
        product = _make_product(
            lifecycle=LifecycleStage.intro, market_share=0.10
        )
        employees = {
            EmployeeId(f"emp-{i:02d}"): _make_employee(f"emp-{i:02d}", skill=5)
            for i in range(4)
        }
        state = _make_state(
            products={ProductId("prod-saas-1"): product},
            employees=employees,
        )
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        # intro gain: 0.10 + 0.02 = 0.12; int(0.12 * 20 * 12) = 28
        assert prod.revenue_per_week == 28

    def test_revenue_is_zero_when_total_skill_zero(self) -> None:
        """Given: no employees (total_skill=0)
        When: tick_products
        Then: revenue_per_week == 0
        """
        product = _make_product(market_share=0.50)
        state = _make_state(
            products={ProductId("prod-saas-1"): product},
            employees={},
        )
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.revenue_per_week == 0


# ---------------------------------------------------------------------------
# Pure-function / immutability contract
# ---------------------------------------------------------------------------


class TestTickProductsImmutability:
    """tick_products is pure: input state is NEVER mutated."""

    def test_input_state_is_not_mutated(self) -> None:
        """Given: any state
        When: tick_products(state, rng)
        Then: input state retains its original product values
        """
        product = _make_product(
            lifecycle=LifecycleStage.intro,
            weeks_in_stage=0,
            market_share=0.05,
        )
        state = _make_state(products={ProductId("prod-saas-1"): product})
        snapshot = dataclasses.replace(
            state,
            products=dict(state.products),
            competitors=dict(state.competitors),
            employees=dict(state.employees),
        )
        _ = tick_products(state, GameRNG(42))
        assert state == snapshot
        assert dict(state.products) == snapshot.products
        assert dict(state.competitors) == snapshot.competitors


# ---------------------------------------------------------------------------
# Determinism (frozen expected values for seed=42, advance 1 tick)
# ---------------------------------------------------------------------------


class TestTickProductsDeterminism:
    """Same inputs + same seed → same output, frozen."""

    def test_same_seed_same_result(self) -> None:
        """Two engines with seed=42 produce the same state_hash after 1 tick."""
        state_a = _make_state(seed=42)
        state_b = _make_state(seed=42)
        result_a = tick_products(state_a, GameRNG(42))
        result_b = tick_products(state_b, GameRNG(42))
        assert state_hash(result_a) == state_hash(result_b)

    def test_frozen_seed_42_advance_1_tick_intro_product(self) -> None:
        """Given: default _make_state() (seed=42, 4 employees skill=10, 1 SaaS
        product at intro share=0.05, default 3 competitors)
        When: tick_products(state, GameRNG(42))
        Then: product weeks_in_stage=1, market_share=0.07,
              revenue_per_week=int(0.07*40*12)=33
        """
        state = _make_state(seed=42)
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        assert prod.lifecycle == LifecycleStage.intro
        assert prod.weeks_in_stage == 1
        assert prod.market_share == pytest.approx(0.07)
        assert prod.revenue_per_week == 33

    def test_frozen_full_state_hash_after_1_tick_seed_42(self) -> None:
        """Lock the post-tick state_hash for the seed=42 default scenario.

        DO NOT update the frozen hash without a plan change + a recorded
        rationale in .omo/evidence/task-12-htop-tycoon.txt.
        """
        state = _make_state(seed=42)
        result = tick_products(state, GameRNG(42))
        digest = state_hash(result)
        assert digest == FROZEN_HASH_AFTER_1_TICK_SEED_42, (
            f"Determinism invariant broken. actual={digest} "
            f"expected={FROZEN_HASH_AFTER_1_TICK_SEED_42}"
        )


# ---------------------------------------------------------------------------
# Static guard: no event_bus.publish in product_market.py
# ---------------------------------------------------------------------------


class TestNoEventBusPublishInProductMarket:
    """product_market.py must NOT call event_bus.publish.

    Anti-pattern from AGENTS.md: ``event_bus.publish`` calls inside action
    functions or metrics collectors are forbidden. tick_products is a pure
    function; the caller (TickEngine / orchestrator) dispatches events.
    """

    PRODUCT_MARKET_PATH = (
        Path(__file__).parent.parent
        / "src"
        / "htop_tycoon"
        / "engine"
        / "product_market.py"
    )

    def test_product_market_module_file_exists(self) -> None:
        """Sanity: the production module under test must exist on disk."""
        assert self.PRODUCT_MARKET_PATH.exists(), (
            f"{self.PRODUCT_MARKET_PATH} missing"
        )

    def test_no_event_bus_publish_call_in_product_market(self) -> None:
        """Given: src/htop_tycoon/engine/product_market.py
        When: scanned for ``event_bus.publish(`` and ``bus.publish(``
        Then: zero matches
        """
        content = self.PRODUCT_MARKET_PATH.read_text(encoding="utf-8")
        pattern = re.compile(r"\b(event_bus|bus)\.publish\s*\(")
        offenders: list[tuple[int, str]] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            for match in pattern.finditer(line):
                offenders.append((line_no, match.group(0)))
        assert offenders == [], (
            "product_market.py must not call event_bus.publish(...). "
            "Engine returns events; the caller dispatches. Offending lines: "
            + ", ".join(f"L{ln}:{tok}" for ln, tok in offenders)
        )

    def test_no_import_of_event_bus_in_product_market(self) -> None:
        """product_market.py must not import or reference EventBus."""
        content = self.PRODUCT_MARKET_PATH.read_text(encoding="utf-8")
        assert "EventBus" not in content, (
            "product_market.py must not import or reference EventBus "
            "(pure engine logic; no side-effect dispatch)"
        )


# ---------------------------------------------------------------------------
# Edge cases (state shape)
# ---------------------------------------------------------------------------


class TestTickProductsEmptyState:
    """Edge cases: no products / no competitors."""

    def test_no_products_returns_state_unchanged(self) -> None:
        """Given: state with empty products dict
        When: tick_products
        Then: state.products is still empty, no error raised
        """
        state = _make_state(products={})
        result = tick_products(state, GameRNG(42))
        assert result.products == {}

    def test_no_competitors_intro_has_no_cap(self) -> None:
        """Given: no competitors (competitor_avg = 0), intro share grows freely.
        With gain=0.02 and no cap, share goes 0.05 -> 0.07.
        """
        product = _make_product(
            lifecycle=LifecycleStage.intro, market_share=0.05
        )
        state = _make_state(
            products={ProductId("prod-saas-1"): product},
            competitors={},
        )
        result = tick_products(state, GameRNG(42))
        prod = result.products[ProductId("prod-saas-1")]
        # No cap (avg = 0), so share grows by exactly 0.02.
        assert prod.market_share == pytest.approx(0.07)
