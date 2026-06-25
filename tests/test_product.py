"""Tests for T6: domain.product (ProductType + LifecycleStage + Product + lifecycle helpers).

Locks the contract:
- ProductType is a locked enum of exactly 3 values: SaaS, Hardware, Consulting.
- LifecycleStage is a locked enum of exactly 4 values: intro, growth, maturity, decline.
- Product is a frozen dataclass with id, type, lifecycle, weeks_in_stage, market_share,
  revenue_per_week; rejects market_share outside [0.0, 1.0] and weeks_in_stage < 0.
- advance_lifecycle_weeks(product, n, lifecycle_weeks) is a pure function: returns a
  NEW instance via dataclasses.replace (no mutation), transitions at stage boundaries
  (intro=8 -> growth=26 -> maturity=52 -> decline=26), and freezes at decline boundary.
- compute_revenue_per_week(product, total_skill, revenue_per_skill_point) returns
  ``int(product.market_share * total_skill * revenue_per_skill_point)``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.product import (
    LifecycleStage,
    Product,
    ProductType,
    advance_lifecycle_weeks,
    compute_revenue_per_week,
)

# Default lifecycle weeks used in most tests. Mirrors balance.yaml.
LIFECYCLE_WEEKS: dict[str, int] = {"intro": 8, "growth": 26, "maturity": 52, "decline": 26}


def _make_product(
    *,
    lifecycle: LifecycleStage = LifecycleStage.intro,
    weeks_in_stage: int = 0,
    market_share: float = 0.1,
    revenue_per_week: int = 1_000,
    product_type: ProductType = ProductType.SaaS,
    product_id: str = "prod-1",
) -> Product:
    """Construct a Product with sensible defaults for tests."""
    return Product(
        id=product_id,
        type=product_type,
        lifecycle=lifecycle,
        weeks_in_stage=weeks_in_stage,
        market_share=market_share,
        revenue_per_week=revenue_per_week,
    )


# == ProductType enum ========================================================


class TestProductTypeEnum:
    """ProductType is a locked enum of exactly 3 values."""

    def test_has_exactly_three_values(self) -> None:
        """Given: the locked enum
        When: counted
        Then: exactly 3 members
        """
        assert len(ProductType) == 3

    def test_contains_saas(self) -> None:
        """SaaS must be a member."""
        assert hasattr(ProductType, "SaaS")

    def test_contains_hardware(self) -> None:
        """Hardware must be a member."""
        assert hasattr(ProductType, "Hardware")

    def test_contains_consulting(self) -> None:
        """Consulting must be a member."""
        assert hasattr(ProductType, "Consulting")


# == LifecycleStage enum =====================================================


class TestLifecycleStageEnum:
    """LifecycleStage is a locked enum of exactly 4 values."""

    def test_has_exactly_four_values(self) -> None:
        """Given: the locked enum
        When: counted
        Then: exactly 4 members
        """
        assert len(LifecycleStage) == 4

    def test_contains_intro(self) -> None:
        """intro must be a member."""
        assert hasattr(LifecycleStage, "intro")

    def test_contains_growth(self) -> None:
        """growth must be a member."""
        assert hasattr(LifecycleStage, "growth")

    def test_contains_maturity(self) -> None:
        """maturity must be a member."""
        assert hasattr(LifecycleStage, "maturity")

    def test_contains_decline(self) -> None:
        """decline must be a member."""
        assert hasattr(LifecycleStage, "decline")

    def test_stage_names_match_balance_yaml_keys(self) -> None:
        """Given: balance.yaml's products.lifecycle_weeks
        When: compared to LifecycleStage member names
        Then: each balance key matches a stage name
        """
        balance = load_balance()
        balance_keys = set(balance["products"]["lifecycle_weeks"].keys())
        stage_names = {stage.name for stage in LifecycleStage}
        assert balance_keys == stage_names


# == Product dataclass =======================================================


class TestProductDataclass:
    """Product is a frozen dataclass with the documented fields and validation."""

    def test_creation_with_valid_args(self) -> None:
        """Given: a complete set of valid Product fields
        When: Product(...) is constructed
        Then: the instance exposes all fields with the given values
        """
        p = _make_product()
        assert p.id == "prod-1"
        assert p.type == ProductType.SaaS
        assert p.lifecycle == LifecycleStage.intro
        assert p.weeks_in_stage == 0
        assert p.market_share == 0.1
        assert p.revenue_per_week == 1_000

    def test_is_frozen(self) -> None:
        """Product must be a frozen dataclass; field reassignment raises."""
        p = _make_product()
        with pytest.raises(FrozenInstanceError):
            p.market_share = 0.5  # type: ignore[misc]

    def test_rejects_market_share_above_one(self) -> None:
        """Given: market_share > 1.0
        When: Product(...) is constructed
        Then: ValueError is raised (plan QA failure scenario)
        """
        with pytest.raises(ValueError, match="market_share"):
            _make_product(market_share=1.5)

    def test_rejects_market_share_below_zero(self) -> None:
        """Given: market_share < 0.0
        When: Product(...) is constructed
        Then: ValueError is raised
        """
        with pytest.raises(ValueError, match="market_share"):
            _make_product(market_share=-0.1)

    def test_accepts_market_share_zero(self) -> None:
        """market_share=0.0 is the lower boundary and must be allowed."""
        p = _make_product(market_share=0.0)
        assert p.market_share == 0.0

    def test_accepts_market_share_one(self) -> None:
        """market_share=1.0 is the upper boundary and must be allowed."""
        p = _make_product(market_share=1.0)
        assert p.market_share == 1.0

    def test_rejects_non_numeric_market_share(self) -> None:
        """Given: market_share is a string
        When: Product(...) is constructed
        Then: ValueError is raised
        """
        with pytest.raises(ValueError, match="market_share"):
            _make_product(market_share="0.5")  # type: ignore[arg-type]

    def test_rejects_negative_weeks_in_stage(self) -> None:
        """Given: weeks_in_stage < 0
        When: Product(...) is constructed
        Then: ValueError is raised
        """
        with pytest.raises(ValueError, match="weeks_in_stage"):
            _make_product(weeks_in_stage=-1)

    def test_rejects_non_int_weeks_in_stage(self) -> None:
        """Given: weeks_in_stage is a float
        When: Product(...) is constructed
        Then: ValueError is raised
        """
        with pytest.raises(ValueError, match="weeks_in_stage"):
            _make_product(weeks_in_stage=0.5)  # type: ignore[arg-type]

    def test_rejects_bool_weeks_in_stage(self) -> None:
        """bool is a subclass of int; reject it explicitly."""
        with pytest.raises(ValueError, match="weeks_in_stage"):
            _make_product(weeks_in_stage=True)  # type: ignore[arg-type]

    def test_rejects_negative_revenue_per_week(self) -> None:
        """revenue_per_week must be non-negative (sanity default)."""
        with pytest.raises(ValueError, match="revenue_per_week"):
            _make_product(revenue_per_week=-1)

    def test_rejects_non_int_revenue_per_week(self) -> None:
        """revenue_per_week must be a strict int (no bool, no float)."""
        with pytest.raises(ValueError, match="revenue_per_week"):
            _make_product(revenue_per_week=1.5)  # type: ignore[arg-type]


# == advance_lifecycle_weeks =================================================


class TestAdvanceLifecycleWeeks:
    """advance_lifecycle_weeks is a pure helper that returns a NEW Product instance."""

    def test_zero_weeks_returns_new_instance_with_same_values(self) -> None:
        """Given: a Product in intro, weeks_in_stage=3
        When: advance_lifecycle_weeks(p, 0, LIFECYCLE_WEEKS)
        Then: returns a NEW Product with the same field values
        """
        p = _make_product(weeks_in_stage=3)
        p2 = advance_lifecycle_weeks(p, 0, LIFECYCLE_WEEKS)
        assert p2 is not p  # new instance
        assert p2.lifecycle == LifecycleStage.intro
        assert p2.weeks_in_stage == 3

    def test_advances_within_same_stage(self) -> None:
        """Given: a Product in intro, weeks_in_stage=0
        When: advance_lifecycle_weeks(p, 5, LIFECYCLE_WEEKS)
        Then: still intro, weeks_in_stage=5
        """
        p = _make_product(weeks_in_stage=0)
        p2 = advance_lifecycle_weeks(p, 5, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.intro
        assert p2.weeks_in_stage == 5

    def test_advances_to_stage_boundary(self) -> None:
        """Given: a Product in intro, weeks_in_stage=0
        When: advance_lifecycle_weeks(p, 8, LIFECYCLE_WEEKS)
        Then: still intro, weeks_in_stage=8 (boundary, no transition yet)
        """
        p = _make_product(weeks_in_stage=0)
        p2 = advance_lifecycle_weeks(p, 8, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.intro
        assert p2.weeks_in_stage == 8

    def test_transitions_intro_to_growth_at_next_week(self) -> None:
        """Plan QA happy scenario:
        Product(intro, weeks_in_stage=8).advance(1) -> growth, weeks_in_stage=1.
        """
        p = _make_product(weeks_in_stage=8)
        p2 = advance_lifecycle_weeks(p, 1, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.growth
        assert p2.weeks_in_stage == 1

    def test_transitions_growth_to_maturity_at_boundary(self) -> None:
        """Given: Product in growth, weeks_in_stage=26
        When: advance_lifecycle_weeks(p, 1, LIFECYCLE_WEEKS)
        Then: transitions to maturity, weeks_in_stage=1
        """
        p = _make_product(lifecycle=LifecycleStage.growth, weeks_in_stage=26)
        p2 = advance_lifecycle_weeks(p, 1, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.maturity
        assert p2.weeks_in_stage == 1

    def test_transitions_maturity_to_decline_at_boundary(self) -> None:
        """Given: Product in maturity, weeks_in_stage=52
        When: advance_lifecycle_weeks(p, 1, LIFECYCLE_WEEKS)
        Then: transitions to decline, weeks_in_stage=1
        """
        p = _make_product(lifecycle=LifecycleStage.maturity, weeks_in_stage=52)
        p2 = advance_lifecycle_weeks(p, 1, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.decline
        assert p2.weeks_in_stage == 1

    def test_full_lifecycle_intro_to_decline_takes_112_weeks(self) -> None:
        """The complete 4-stage lifecycle sums to 8+26+52+26 = 112 weeks.

        Given: Product in intro, weeks_in_stage=0
        When: advance_lifecycle_weeks(p, 112, LIFECYCLE_WEEKS)
        Then: stage=decline, weeks_in_stage=26 (decline fully consumed)
        """
        p = _make_product(weeks_in_stage=0)
        p2 = advance_lifecycle_weeks(p, 112, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.decline
        assert p2.weeks_in_stage == 26

    def test_advance_past_decline_freezes_at_boundary(self) -> None:
        """Given: Product in decline, weeks_in_stage=26
        When: advance_lifecycle_weeks(p, 1, LIFECYCLE_WEEKS)
        Then: stays at decline, weeks_in_stage=26 (freeze, end-of-lifecycle)

        Design decision: once the decline stage is fully consumed, the lifecycle
        is complete. The product is frozen at the decline boundary. The engine
        (T12+) can detect "end of lifecycle" via weeks_in_stage >= decline_weeks.
        """
        p = _make_product(lifecycle=LifecycleStage.decline, weeks_in_stage=26)
        p2 = advance_lifecycle_weeks(p, 1, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.decline
        assert p2.weeks_in_stage == 26

    def test_advance_past_decline_large_n_still_freezes(self) -> None:
        """Given: Product in decline, weeks_in_stage=26
        When: advance_lifecycle_weeks(p, 1000, LIFECYCLE_WEEKS)
        Then: stays at decline, weeks_in_stage=26 (still frozen)
        """
        p = _make_product(lifecycle=LifecycleStage.decline, weeks_in_stage=26)
        p2 = advance_lifecycle_weeks(p, 1000, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.decline
        assert p2.weeks_in_stage == 26

    def test_advance_113_weeks_from_intro_ends_lifecycle(self) -> None:
        """Plan acceptance: lifecycle ends at week 113 (8+26+52+26+1 = 113).

        Given: Product in intro, weeks_in_stage=0
        When: advance_lifecycle_weeks(p, 113, LIFECYCLE_WEEKS)
        Then: stage=decline, weeks_in_stage=26 (lifecycle ended; frozen)
        """
        p = _make_product(weeks_in_stage=0)
        p2 = advance_lifecycle_weeks(p, 113, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.decline
        assert p2.weeks_in_stage == 26

    def test_advance_within_maturity_large_n(self) -> None:
        """Given: Product in maturity, weeks_in_stage=10
        When: advance_lifecycle_weeks(p, 30, LIFECYCLE_WEEKS)
        Then: overflow 30-42 -> wait, 10+30=40, 40<=52, stays in maturity, weeks=40
        """
        p = _make_product(lifecycle=LifecycleStage.maturity, weeks_in_stage=10)
        p2 = advance_lifecycle_weeks(p, 30, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.maturity
        assert p2.weeks_in_stage == 40

    def test_advance_spans_three_stages(self) -> None:
        """Given: Product in intro, weeks_in_stage=4
        When: advance_lifecycle_weeks(p, 35, LIFECYCLE_WEEKS)
        Then: 4+35=39 total. intro(8) consumed -> 31, growth(26) consumed -> 5,
              remaining 5 weeks in maturity.
        """
        p = _make_product(weeks_in_stage=4)
        p2 = advance_lifecycle_weeks(p, 35, LIFECYCLE_WEEKS)
        assert p2.lifecycle == LifecycleStage.maturity
        assert p2.weeks_in_stage == 5

    def test_negative_n_raises_value_error(self) -> None:
        """advance_lifecycle_weeks must reject negative n."""
        p = _make_product()
        with pytest.raises(ValueError, match="n"):
            advance_lifecycle_weeks(p, -1, LIFECYCLE_WEEKS)

    def test_does_not_mutate_original(self) -> None:
        """advance_lifecycle_weeks is pure: original Product is unchanged."""
        p = _make_product(weeks_in_stage=3)
        _ = advance_lifecycle_weeks(p, 10, LIFECYCLE_WEEKS)
        # Original still has weeks_in_stage=3, lifecycle=intro
        assert p.weeks_in_stage == 3
        assert p.lifecycle == LifecycleStage.intro

    def test_preserves_other_fields(self) -> None:
        """advance_lifecycle_weeks must NOT touch id, type, market_share, revenue_per_week."""
        p = _make_product(weeks_in_stage=8)
        p2 = advance_lifecycle_weeks(p, 1, LIFECYCLE_WEEKS)
        assert p2.id == p.id
        assert p2.type == p.type
        assert p2.market_share == p.market_share
        assert p2.revenue_per_week == p.revenue_per_week

    def test_can_be_chained_through_full_lifecycle(self) -> None:
        """Simulate the full lifecycle via chained advance(1) calls.

        Given: Product in intro, weeks_in_stage=0
        When: 113 sequential advance(1) calls
        Then: product ends at decline, weeks_in_stage=26 (frozen)
        """
        p = _make_product(weeks_in_stage=0)
        for _ in range(113):
            p = advance_lifecycle_weeks(p, 1, LIFECYCLE_WEEKS)
        assert p.lifecycle == LifecycleStage.decline
        assert p.weeks_in_stage == 26


# == compute_revenue_per_week ================================================


class TestComputeRevenuePerWeek:
    """compute_revenue_per_week returns int(market_share * total_skill * rp)."""

    def test_zero_skill_returns_zero(self) -> None:
        """Given: total_skill=0
        When: compute_revenue_per_week(...)
        Then: returns 0
        """
        p = _make_product(market_share=0.5)
        assert compute_revenue_per_week(p, total_skill=0, revenue_per_skill_point=12) == 0

    def test_zero_market_share_returns_zero(self) -> None:
        """Given: market_share=0.0
        When: compute_revenue_per_week(...)
        Then: returns 0
        """
        p = _make_product(market_share=0.0)
        assert compute_revenue_per_week(p, total_skill=10, revenue_per_skill_point=12) == 0

    def test_scales_linearly_with_market_share(self) -> None:
        """Given: market_share doubled (0.1 -> 0.2) with all else equal
        When: compute_revenue_per_week is called twice
        Then: the second result is exactly 2x the first
        """
        p1 = _make_product(market_share=0.1)
        p2 = _make_product(market_share=0.2)
        r1 = compute_revenue_per_week(p1, total_skill=10, revenue_per_skill_point=12)
        r2 = compute_revenue_per_week(p2, total_skill=10, revenue_per_skill_point=12)
        assert r2 == 2 * r1

    def test_scales_linearly_with_total_skill(self) -> None:
        """Given: total_skill doubled (5 -> 10) with all else equal
        When: compute_revenue_per_week is called twice
        Then: the second result is exactly 2x the first
        """
        p = _make_product(market_share=0.5)
        r1 = compute_revenue_per_week(p, total_skill=5, revenue_per_skill_point=12)
        r2 = compute_revenue_per_week(p, total_skill=10, revenue_per_skill_point=12)
        assert r2 == 2 * r1

    def test_scales_linearly_with_revenue_per_skill_point(self) -> None:
        """Given: revenue_per_skill_point doubled (10 -> 20) with all else equal
        When: compute_revenue_per_week is called twice
        Then: the second result is exactly 2x the first
        """
        p = _make_product(market_share=0.5)
        r1 = compute_revenue_per_week(p, total_skill=10, revenue_per_skill_point=10)
        r2 = compute_revenue_per_week(p, total_skill=10, revenue_per_skill_point=20)
        assert r2 == 2 * r1

    def test_formula_exact(self) -> None:
        """Given: market_share=0.25, total_skill=8, revenue_per_skill_point=12
        When: compute_revenue_per_week(...)
        Then: returns int(0.25 * 8 * 12) = int(24.0) = 24
        """
        p = _make_product(market_share=0.25)
        result = compute_revenue_per_week(p, total_skill=8, revenue_per_skill_point=12)
        assert result == 24

    def test_returns_int_type(self) -> None:
        """Given: a non-integer-result product (e.g. market_share=0.33)
        When: compute_revenue_per_week(...)
        Then: returns an int (truncated, not rounded)
        """
        p = _make_product(market_share=0.33)
        result = compute_revenue_per_week(p, total_skill=10, revenue_per_skill_point=12)
        assert isinstance(result, int)
        # 0.33 * 10 * 12 = 39.6 -> int(39.6) = 39
        assert result == 39

    def test_uses_balance_yaml_default(self) -> None:
        """Given: revenue_per_skill_point from balance.yaml (= 12)
        When: compute_revenue_per_week with total_skill=10, market_share=0.5
        Then: returns int(0.5 * 10 * 12) = 60
        """
        balance = load_balance()
        rpsp = int(balance["products"]["revenue_per_skill_point_per_week"])
        p = _make_product(market_share=0.5)
        assert compute_revenue_per_week(p, total_skill=10, revenue_per_skill_point=rpsp) == 60

    def test_full_market_share_full_skill(self) -> None:
        """Given: market_share=1.0, total_skill=10, revenue_per_skill_point=12
        When: compute_revenue_per_week(...)
        Then: returns 120
        """
        p = _make_product(market_share=1.0)
        assert compute_revenue_per_week(p, total_skill=10, revenue_per_skill_point=12) == 120


# == sanity: Product does not mutate via dataclasses.replace outside the helper


def test_dataclasses_replace_works_on_product() -> None:
    """dataclasses.replace must work (returns a new instance, leaves the original intact)."""
    p = _make_product()
    p2 = dataclasses.replace(p, weeks_in_stage=5)
    assert p.weeks_in_stage == 0  # original unchanged
    assert p2.weeks_in_stage == 5
    assert p2.lifecycle == LifecycleStage.intro
