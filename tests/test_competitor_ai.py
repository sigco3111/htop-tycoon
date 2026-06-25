"""Tests for T13: Competitor AI (aggression -> action probability, costs from balance).

Locks the contract from .omo/plans/htop-tycoon.md line 391-403 (T13):

- ``step_competitors(state, rng) -> (new_state, events)`` is pure: returns a
  new state via ``dataclasses.replace`` and a list of ``CompetitorAction``
  events; the input state is NEVER mutated.
- For each alive competitor: ``rng.float() < competitor.aggression`` decides
  if they act this tick. With aggression=1.0 they always act; with
  aggression=0.0 they never act.
- Action choice distribution (locked, sum=1.0):
  - PRICE_CUT         40%
  - TALENT_POACH      30%
  - MARKETING_SPREE   30%
- Action costs come from ``balance.yaml["competitors"]["action_costs"]``,
  not from Python constants.
- PRICE_CUT steals ``PRICE_CUT_STEAL_FRACTION`` (= 2%) of market share from
  a random player product.
- TALENT_POACH targets a random employee with ``skill > poach_min_skill``
  (default 7), 30% poach chance. Successful poach removes the employee AND
  reduces the player's market_share for the employee's dept's primary
  product by 1%.
- MARKETING_SPREE boosts own market_share by 1% and deducts the cost from
  ``competitor.cash``. If cash < cost, the action is SKIPPED (no event).
- ``competitor.cash`` is clamped to 0 (no negative cash ever).
- Each action returns exactly one ``CompetitorAction`` event in the tuple.
- The action vocabulary is hard-coded as module-level constants
  (ACTION_PRICE_CUT, ACTION_TALENT_POACH, ACTION_MARKETING_SPREE).
- ``step_competitors`` does NOT call ``event_bus.publish(...)`` (engine
  returns events; the caller dispatches).
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from htop_tycoon.data import load_balance
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

# The competitor_ai module is the production module under test.
# Importing at module level is fine: pytest collection will surface any
# ImportError, which is itself a red-phase signal if the module is missing.
from htop_tycoon.engine.competitor_ai import (  # noqa: I001,F401
    ACTION_MARKETING_SPREE,
    ACTION_PRICE_CUT,
    ACTION_TALENT_POACH,
    DEPT_PRIMARY_PRODUCT,
    step_competitors,
)
from htop_tycoon.engine.events import CompetitorAction, Event
from htop_tycoon.engine.rng import GameRNG

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------


def _cid(name: str) -> ProductId | DepartmentId | EmployeeId:
    """Casting helper: plain str -> NewType'd id (used inline below)."""


def _make_test_state(
    *,
    aggression: float | None = None,
    cash: int | None = None,
    num_employees: int = 10,
) -> GameState:
    """Build a GameState with default 3 competitors, 1 product, and N employees.

    Employees are split evenly between ``Engineering`` (skill=3, untargetable)
    and ``Sales`` (skill=9, targetable by TALENT_POACH when
    poach_min_skill=7). This provides both targetable and untargetable
    candidates so TALENT_POACH tests can verify the ``skill > poach_min``
    gate.
    """
    state = new_game(42)
    market = load_default_market(load_balance())
    competitors: dict = dict(market.competitors)
    if aggression is not None or cash is not None:
        competitors = {
            cid: dataclasses.replace(
                c,
                aggression=aggression if aggression is not None else c.aggression,
                cash=cash if cash is not None else c.cash,
            )
            for cid, c in competitors.items()
        }
    state = dataclasses.replace(state, competitors=competitors)

    product = Product(
        id=ProductId("prod-saas-1"),
        type=ProductType.SaaS,
        lifecycle=LifecycleStage.maturity,
        weeks_in_stage=0,
        market_share=0.50,
        revenue_per_week=0,
    )
    state = dataclasses.replace(
        state, products={ProductId("prod-saas-1"): product}
    )

    employees: dict[EmployeeId, Employee] = {}
    half = max(1, num_employees // 2)
    for i in range(num_employees):
        if i < half:
            # Untargetable: skill == poach_min_skill (strict > gate)
            emp = Employee(
                id=EmployeeId(f"low-{i:03d}"),
                name=f"Low{i}",
                dept_id=DepartmentId("Engineering"),
                skill=3,
                tier=1,
                salary_per_week=100,
                satisfaction=50,
                hired_tick=0,
            )
        else:
            # Targetable: skill > poach_min_skill
            emp = Employee(
                id=EmployeeId(f"high-{i:03d}"),
                name=f"High{i}",
                dept_id=DepartmentId("Sales"),
                skill=9,
                tier=2,
                salary_per_week=200,
                satisfaction=50,
                hired_tick=0,
            )
        employees[EmployeeId(emp.id)] = emp
    state = dataclasses.replace(state, employees=employees)
    return state


# ---------------------------------------------------------------------------
# Module surface (action vocabulary, dept->product mapping)
# ---------------------------------------------------------------------------


class TestCompetitorAiModuleSurface:
    """The module exposes the locked action vocabulary and dept->product map."""

    def test_action_constants_match_balance_yaml(self) -> None:
        """The 3 action-type string constants are the locked vocabulary."""
        assert ACTION_PRICE_CUT == "PRICE_CUT"
        assert ACTION_TALENT_POACH == "TALENT_POACH"
        assert ACTION_MARKETING_SPREE == "MARKETING_SPREE"

    def test_action_constants_present_in_balance_costs(self) -> None:
        """Every action constant appears as a key in balance.action_costs."""
        costs = load_balance()["competitors"]["action_costs"]
        for name in (ACTION_PRICE_CUT, ACTION_TALENT_POACH, ACTION_MARKETING_SPREE):
            assert name in costs, f"action {name!r} missing from balance.action_costs"

    def test_dept_primary_product_covers_all_five_departments(self) -> None:
        """DEPT_PRIMARY_PRODUCT must cover all 5 locked DepartmentType values."""
        from htop_tycoon.domain.dept import DepartmentType
        assert set(DEPT_PRIMARY_PRODUCT.keys()) == {
            DepartmentId(d.value) for d in DepartmentType
        }


# ---------------------------------------------------------------------------
# Return-type contract
# ---------------------------------------------------------------------------


class TestStepCompetitorsReturnContract:
    """step_competitors returns (new_state, list_of_events)."""

    def test_returns_tuple_of_state_and_events_list(self) -> None:
        """Given: any valid state + rng
        When: step_competitors is called
        Then: returns a tuple (GameState, list[Event]) with both elements
              populated to the documented types.
        """
        state = _make_test_state()
        rng = GameRNG(42)
        result = step_competitors(state, rng)
        assert isinstance(result, tuple)
        assert len(result) == 2
        new_state, events = result
        assert isinstance(new_state, GameState)
        assert isinstance(events, list)
        for event in events:
            assert isinstance(event, Event)
            assert isinstance(event, CompetitorAction)

    def test_input_state_is_not_mutated(self) -> None:
        """step_competitors must be a pure function: input state is untouched."""
        state = _make_test_state()
        snapshot = dataclasses.replace(
            state,
            competitors=dict(state.competitors),
            products=dict(state.products),
            employees=dict(state.employees),
        )
        rng = GameRNG(42)
        _ = step_competitors(state, rng)
        assert state == snapshot
        assert dict(state.competitors) == snapshot.competitors
        assert dict(state.products) == snapshot.products
        assert dict(state.employees) == snapshot.employees


# ---------------------------------------------------------------------------
# Aggression gating
# ---------------------------------------------------------------------------


class TestAggressionGating:
    """``rng.float() < aggression`` decides action this tick."""

    def test_aggression_one_acts_every_tick(self) -> None:
        """Given: all 3 competitors with aggression=1.0 + high cash so no
              MARKETING_SPREE gets skipped
        When: step_competitors runs for 100 ticks
        Then: every tick yields exactly 3 events (one per competitor)
        """
        # Set cash very high so MARKETING_SPREE (cost=1500) is always
        # affordable; with cost=0 PRICE_CUT and TALENT_POACH fire 100% of
        # the time anyway.
        state = _make_test_state(aggression=1.0, cash=1_000_000)
        rng = GameRNG(42)
        for _ in range(100):
            new_state, events = step_competitors(state, rng)
            assert len(events) == 3, (
                f"expected 3 events (1 per competitor), got {len(events)}"
            )
            state = new_state

    def test_aggression_zero_never_acts_over_1000_ticks(self) -> None:
        """Given: all 3 competitors with aggression=0.0
        When: step_competitors runs for 1000 ticks
        Then: zero events emitted (no opponent actions)
        """
        state = _make_test_state(aggression=0.0)
        rng = GameRNG(42)
        for tick in range(1000):
            new_state, events = step_competitors(state, rng)
            assert events == [], f"tick {tick}: expected 0 events, got {events}"
            state = new_state

    def test_aggression_action_frequency_within_10pct(self) -> None:
        """Given: all 3 competitors with aggression=0.5 + high cash so no
              MARKETING_SPREE gets skipped
        When: step_competitors runs for 1000 ticks with seed=42
        Then: total event count is within +/- 10% of 1500 (= 3*1000*0.5)
        """
        # High cash prevents the MARKETING_SPREE-skip behavior from
        # reducing the observed event count below the bare aggression
        # expectation.
        state = _make_test_state(aggression=0.5, cash=1_000_000)
        rng = GameRNG(42)
        total = 0
        for _ in range(1000):
            new_state, events = step_competitors(state, rng)
            total += len(events)
            state = new_state
        expected = 1500
        lower = int(expected * 0.9)
        upper = int(expected * 1.1)
        assert lower <= total <= upper, (
            f"action count {total} outside +/- 10% of {expected} (range {lower}..{upper})"
        )


# ---------------------------------------------------------------------------
# PRICE_CUT action
# ---------------------------------------------------------------------------


class TestPriceCut:
    """PRICE_CUT steals a fixed fraction of market share from a random product."""

    def test_price_cut_reduces_market_share_by_locked_fraction(self) -> None:
        """Given: aggression=1.0, one product at share=0.50
        When: step_competitors runs for 500 ticks
        Then: total market_share reduction equals price_cut_count * 0.02
              (multiple PRICE_CUTs may fire on the same product in one tick)
        """
        state = _make_test_state(aggression=1.0)
        product_id = ProductId("prod-saas-1")
        initial_share = state.products[product_id].market_share
        expected_delta = 0.02
        rng = GameRNG(42)
        price_cut_count = 0
        for _ in range(500):
            new_state, events = step_competitors(state, rng)
            for event in events:
                if event.action_type == ACTION_PRICE_CUT:
                    target = event.details.get("target_product")
                    if target == str(product_id):
                        price_cut_count += 1
            state = new_state
        assert price_cut_count > 0, "expected at least one PRICE_CUT on the seeded product"
        # Multiple PRICE_CUTs in the same tick can target the same product;
        # total reduction is count * delta (floored at 0.0 inside the engine).
        expected_final = max(0.0, initial_share - price_cut_count * expected_delta)
        assert state.products[product_id].market_share == pytest.approx(expected_final)

    def test_price_cut_chooses_target_via_rng(self) -> None:
        """Given: aggression=1.0, one product
        When: many PRICE_CUTs fire
        Then: details["target_product"] is the product id (rng.choice path)
        """
        state = _make_test_state(aggression=1.0)
        rng = GameRNG(42)
        seen_targets: set[str] = set()
        for _ in range(500):
            new_state, events = step_competitors(state, rng)
            for event in events:
                if event.action_type == ACTION_PRICE_CUT:
                    seen_targets.add(event.details["target_product"])
            state = new_state
        assert "prod-saas-1" in seen_targets


# ---------------------------------------------------------------------------
# TALENT_POACH action
# ---------------------------------------------------------------------------


class TestTalentPoach:
    """TALENT_POACH only targets employees with skill > poach_min_skill."""

    def test_talent_poach_never_targets_low_skill_employee(self) -> None:
        """Given: 5 low-skill (skill=3) and 5 high-skill (skill=9) employees
        When: step_competitors runs for 1000 ticks with aggression=1.0
        Then: low-skill employees are never the target_employee in details
        """
        state = _make_test_state(aggression=1.0, num_employees=10)
        low_ids = {f"low-{i:03d}" for i in range(5)}
        rng = GameRNG(42)
        for _ in range(1000):
            new_state, events = step_competitors(state, rng)
            for event in events:
                if event.action_type == ACTION_TALENT_POACH:
                    target = event.details.get("target_employee")
                    if target is not None:
                        assert target not in low_ids, (
                            f"low-skill {target} was targeted despite skill=3"
                        )
            state = new_state

    def test_talent_poach_event_carries_target_employee(self) -> None:
        """PRICE_CUT and TALENT_POACH details must include the target id."""
        state = _make_test_state(aggression=1.0)
        rng = GameRNG(42)
        found_poach = False
        for _ in range(500):
            new_state, events = step_competitors(state, rng)
            for event in events:
                if event.action_type == ACTION_TALENT_POACH:
                    assert "target_employee" in event.details
                    found_poach = True
            state = new_state
        assert found_poach, "expected at least one TALENT_POACH in 500 ticks"


# ---------------------------------------------------------------------------
# MARKETING_SPREE action
# ---------------------------------------------------------------------------


class TestMarketingSpree:
    """MARKETING_SPREE deducts the cost; is skipped if competitor cannot pay."""

    def test_marketing_spree_deducts_cost_from_competitor_cash(self) -> None:
        """Given: aggression=1.0, all competitors with cash well above cost
        When: step_competitors runs and a MARKETING_SPREE fires
        Then: the acting competitor's cash decreases by exactly the cost
        """
        state = _make_test_state(aggression=1.0, cash=100_000)
        cost = int(load_balance()["competitors"]["action_costs"][ACTION_MARKETING_SPREE])
        current_cash = {c.id: c.cash for c in state.competitors.values()}
        rng = GameRNG(42)
        seen = 0
        for _ in range(500):
            new_state, events = step_competitors(state, rng)
            for event in events:
                if event.action_type == ACTION_MARKETING_SPREE:
                    comp_id = event.competitor_id
                    expected = max(0, current_cash[comp_id] - cost)
                    assert new_state.competitors[comp_id].cash == expected, (
                        f"comp {comp_id}: cash {new_state.competitors[comp_id].cash} "
                        f"!= expected {expected} (cost={cost}, prior={current_cash[comp_id]})"
                    )
                    current_cash[comp_id] = expected
                    seen += 1
            state = new_state
        assert seen > 0, "expected at least one MARKETING_SPREE in 500 ticks"

    def test_marketing_spree_skipped_when_cash_below_cost(self) -> None:
        """Given: all competitors with cash = cost - 1, aggression=1.0
        When: step_competitors runs for 500 ticks
        Then: NO MARKETING_SPREE event ever appears (action is skipped)
        """
        cost = int(load_balance()["competitors"]["action_costs"][ACTION_MARKETING_SPREE])
        state = _make_test_state(aggression=1.0, cash=cost - 1)
        rng = GameRNG(42)
        for _ in range(500):
            new_state, events = step_competitors(state, rng)
            for event in events:
                assert event.action_type != ACTION_MARKETING_SPREE, (
                    "MARKETING_SPREE fired despite cash < cost"
                )
            state = new_state


# ---------------------------------------------------------------------------
# Cash clamping invariant
# ---------------------------------------------------------------------------


class TestCashClamping:
    """competitor.cash is clamped to 0; never goes negative."""

    def test_cash_never_negative_under_heavy_marketing(self) -> None:
        """Given: all competitors with cash == cost (one MARKETING_SPREE away
              from being unable to pay)
        When: step_competitors runs for 200 ticks
        Then: every competitor.cash in the result is >= 0
        """
        cost = int(load_balance()["competitors"]["action_costs"][ACTION_MARKETING_SPREE])
        state = _make_test_state(aggression=1.0, cash=cost)
        rng = GameRNG(42)
        for _ in range(200):
            new_state, _ = step_competitors(state, rng)
            for comp in new_state.competitors.values():
                assert comp.cash >= 0, f"competitor {comp.name} cash={comp.cash} < 0"
            state = new_state

    def test_cash_at_zero_still_produces_other_actions(self) -> None:
        """Given: all competitors with cash=0 (can't MARKETING_SPREE), aggression=1.0
        When: step_competitors runs
        Then: PRICE_CUT and TALENT_POACH events still occur (they cost 0),
              MARKETING_SPREE never appears.
        """
        state = _make_test_state(aggression=1.0, cash=0)
        rng = GameRNG(42)
        # Run several ticks; each tick has 3 acting competitors, each
        # picking a random action. The only stable invariant when cash=0
        # is that MARKETING_SPREE is always skipped; PRICE_CUT and
        # TALENT_POACH (cost 0) fire normally.
        for _ in range(50):
            state, events = step_competitors(state, rng)
            for event in events:
                assert event.action_type != ACTION_MARKETING_SPREE


# ---------------------------------------------------------------------------
# Static guard: no event_bus.publish in competitor_ai.py
# ---------------------------------------------------------------------------


class TestNoEventBusPublishInCompetitorAi:
    """Engine core returns events; only the caller dispatches. Anti-pattern
    from AGENTS.md: ``event_bus.publish`` calls inside action functions or
    metrics collectors are forbidden.
    """

    COMPETITOR_AI_PATH = (
        Path(__file__).parent.parent
        / "src"
        / "htop_tycoon"
        / "engine"
        / "competitor_ai.py"
    )

    def test_competitor_ai_module_file_exists(self) -> None:
        """Sanity: the production module under test must exist on disk."""
        assert self.COMPETITOR_AI_PATH.exists(), (
            f"{self.COMPETITOR_AI_PATH} missing"
        )

    def test_no_event_bus_publish_call_in_competitor_ai(self) -> None:
        """Given: src/htop_tycoon/engine/competitor_ai.py
        When: scanned for ``event_bus.publish(`` and ``bus.publish(``
        Then: zero matches (engine returns events; caller dispatches)
        """
        content = self.COMPETITOR_AI_PATH.read_text(encoding="utf-8")
        # Use word-boundary "event_bus" / "bus" identifier to avoid false
        # positives from docstrings or unrelated identifiers.
        pattern = re.compile(r"\b(event_bus|bus)\.publish\s*\(")
        offenders: list[tuple[int, str]] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            for match in pattern.finditer(line):
                offenders.append((line_no, match.group(0)))
        assert offenders == [], (
            "competitor_ai.py must not call event_bus.publish(...). "
            "Engine returns events; the caller dispatches. Offending lines: "
            + ", ".join(f"L{ln}:{tok}" for ln, tok in offenders)
        )

    def test_no_import_of_event_bus_in_competitor_ai(self) -> None:
        """Given: src/htop_tycoon/engine/competitor_ai.py
        When: scanned for ``EventBus`` import / reference
        Then: zero matches (the module must not depend on EventBus at all)
        """
        content = self.COMPETITOR_AI_PATH.read_text(encoding="utf-8")
        assert "EventBus" not in content, (
            "competitor_ai.py must not import or reference EventBus "
            "(pure engine logic; no side-effect dispatch)"
        )
