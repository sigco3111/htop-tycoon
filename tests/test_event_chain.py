"""Tests for T14: Event chain engine (random + conditional) reading events.yaml.

Locks the contract from .omo/plans/htop-tycoon.md line 406-415:

- ``load_events_catalog()`` parses ``events.yaml`` into a list of typed
  ``Event`` objects. Every effect is parsed into the discriminated Effect
  union (locked at 7 variants including ``ScheduleNextEvent`` for chains).
- Every ``condition`` string referenced in yaml MUST have a matching key in
  ``CONDITION_REGISTRY``; loading yaml without one raises ``ValueError``
  (fail-loud, no silent skip).
- ``evaluate_events(state, rng, balance, events_catalog, active_events)``
  evaluates triggers each tick, applies effects, returns updated state +
  fired events + updated active_events list.
- Chains: events can schedule follow-up events via ``ScheduleNextEvent``
  effect (max depth from ``balance.events.max_concurrent_chain_depth``,
  default 4).
- ``evaluate_events`` does NOT call ``event_bus.publish(...)`` — the engine
  returns events; the caller publishes.

QA scenarios from the plan:
- happy: trigger secret_investor_offer conditional with all_depts_unlocked
  -> event fires.
- failure: chain depth exceeds balance limit -> chain truncated.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.event import (
    AddEmployee,
    BoostRevenue,
    Effect,
    Event,
    EventId,
    ProductId,
    RemoveEmployee,
    ScheduleEnding,
    ScheduleNextEvent,
    ShiftMarketShare,
    TriggerSecretInvestor,
)
from htop_tycoon.domain.product import LifecycleStage, Product, ProductType
from htop_tycoon.domain.state import (
    DepartmentId,
    EmployeeId,
    GameState,
    new_game,
)
from htop_tycoon.engine.condition_registry import (
    CONDITION_REGISTRY,
    all_depts_unlocked,
    all_employees_skill_max,
    cash_below_threshold,
    competitor_aggression_high,
    employee_satisfaction_low,
    secret_investor_pending,
)
from htop_tycoon.engine.event_chain import (
    EventInstance,
    evaluate_events,
    load_events_catalog,
)
from htop_tycoon.engine.rng import GameRNG

# ---------------------------------------------------------------------------
# Fixtures: build a state with predictable departments / employees / products.
# ---------------------------------------------------------------------------


def _make_product(
    pid: str = "prod-saas",
    market_share: float = 0.10,
    revenue: int = 1_000,
) -> Product:
    return Product(
        id=ProductId(pid),
        type=ProductType.SaaS,
        lifecycle=LifecycleStage.intro,
        weeks_in_stage=0,
        market_share=market_share,
        revenue_per_week=revenue,
    )


def _make_dept(
    did: str = "dept-eng",
    unlocked: bool = False,
    employee_ids: list[str] | None = None,
) -> Department:
    return Department(
        id=DepartmentId(did),
        type=DepartmentType.Engineering,
        head_employee_id=None,
        employee_ids=[EmployeeId(e) for e in (employee_ids or [])],
        founded_tick=0,
        unlocked=unlocked,
    )


def _make_employee(
    eid: str = "emp-001",
    skill: int = 5,
    satisfaction: int = 60,
    dept_id: str = "dept-eng",
) -> Employee:
    return Employee(
        id=EmployeeId(eid),
        name="테스트",
        dept_id=DepartmentId(dept_id),
        skill=skill,
        tier=1,
        salary_per_week=1000,
        satisfaction=satisfaction,
        hired_tick=0,
    )


def _make_state_with(
    *,
    cash: int = 50_000,
    departments: dict[str, Department] | None = None,
    employees: dict[str, Employee] | None = None,
    products: dict[str, Product] | None = None,
    secret_investor_cleared: bool = False,
) -> GameState:
    base = new_game(42)
    company = dataclasses.replace(base.company, cash=cash)
    return dataclasses.replace(
        base,
        company=company,
        departments={
            DepartmentId(k): v for k, v in (departments or {}).items()
        },
        employees={EmployeeId(k): v for k, v in (employees or {}).items()},
        products={ProductId(k): v for k, v in (products or {}).items()},
        secret_investor_cleared=secret_investor_cleared,
    )


# ---------------------------------------------------------------------------
# Section 1: load_events_catalog — YAML schema + parse.
# ---------------------------------------------------------------------------


class TestLoadEventsCatalogSchema:
    """load_events_catalog() parses the YAML into typed Event objects."""

    def test_load_default_catalog_returns_six_or_more_events(self) -> None:
        """The shipped events.yaml has at least 6 events."""
        catalog = load_events_catalog()
        assert len(catalog) >= 6

    def test_each_event_has_required_fields(self) -> None:
        """Every loaded event carries id, name_ko, description_ko, trigger_type,
        probability_per_tick, and effects."""
        catalog = load_events_catalog()
        for event in catalog:
            assert isinstance(event, Event)
            assert isinstance(event.id, str) and event.id, (
                f"event {event!r} missing id"
            )
            assert isinstance(event.name_ko, str) and event.name_ko.strip(), (
                f"event {event.id} missing name_ko"
            )
            assert isinstance(event.description_ko, str) and event.description_ko.strip(), (
                f"event {event.id} missing description_ko"
            )
            assert event.trigger_type in ("random", "conditional"), (
                f"event {event.id} trigger_type must be random or conditional, "
                f"got {event.trigger_type!r}"
            )
            assert isinstance(event.probability_per_tick, float), (
                f"event {event.id} probability_per_tick must be float, "
                f"got {type(event.probability_per_tick).__name__}"
            )
            assert 0.0 <= event.probability_per_tick <= 1.0, (
                f"event {event.id} probability_per_tick out of [0,1], "
                f"got {event.probability_per_tick}"
            )
            assert isinstance(event.effects, tuple), (
                f"event {event.id} effects must be tuple, "
                f"got {type(event.effects).__name__}"
            )

    def test_catalog_has_at_least_three_random_and_three_conditional(self) -> None:
        """The catalog has >= 3 random events AND >= 3 conditional events."""
        catalog = load_events_catalog()
        random_events = [e for e in catalog if e.trigger_type == "random"]
        conditional_events = [e for e in catalog if e.trigger_type == "conditional"]
        assert len(random_events) >= 3, (
            f"need >= 3 random events, got {len(random_events)}"
        )
        assert len(conditional_events) >= 3, (
            f"need >= 3 conditional events, got {len(conditional_events)}"
        )

    def test_event_ids_are_unique(self) -> None:
        """Every event id in the catalog is unique."""
        catalog = load_events_catalog()
        ids = [e.id for e in catalog]
        assert len(ids) == len(set(ids)), f"duplicate event ids: {ids}"

    def test_load_with_explicit_path(self, tmp_path: Path) -> None:
        """load_events_catalog(path=...) reads from a custom YAML file."""
        yaml_content = (
            "events:\n"
            "  - id: evt-custom\n"
            "    name_ko: '커스텀'\n"
            "    description_ko: '커스텀 이벤트'\n"
            "    trigger_type: random\n"
            "    probability_per_tick: 0.5\n"
            "    condition: null\n"
            "    effects: []\n"
        )
        path = tmp_path / "events.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        catalog = load_events_catalog(path=path)
        assert len(catalog) == 1
        assert catalog[0].id == "evt-custom"
        assert catalog[0].name_ko == "커스텀"
        assert catalog[0].probability_per_tick == 0.5


# ---------------------------------------------------------------------------
# Section 2: load_events_catalog — fail-loud on unknown condition name.
# ---------------------------------------------------------------------------


class TestLoadEventsCatalogFailsLoud:
    """Loading yaml with an unregistered condition name raises ValueError."""

    def test_unknown_condition_raises_value_error(self, tmp_path: Path) -> None:
        """An event whose ``condition`` string is not in CONDITION_REGISTRY
        causes load to fail at startup with ValueError."""
        yaml_content = (
            "events:\n"
            "  - id: evt-bad\n"
            "    name_ko: '잘못된 이벤트'\n"
            "    description_ko: '조건이 등록되지 않은 이벤트'\n"
            "    trigger_type: conditional\n"
            "    probability_per_tick: 0.0\n"
            "    condition: not_a_real_condition_xyz\n"
            "    effects: []\n"
        )
        path = tmp_path / "events.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(ValueError, match="not_a_real_condition_xyz"):
            load_events_catalog(path=path)

    def test_unknown_effect_type_raises_value_error(self, tmp_path: Path) -> None:
        """An effect dict with an unknown ``type`` raises ValueError."""
        yaml_content = (
            "events:\n"
            "  - id: evt-bad-effect\n"
            "    name_ko: '잘못된 효과'\n"
            "    description_ko: '효과 타입이 등록되지 않음'\n"
            "    trigger_type: random\n"
            "    probability_per_tick: 0.1\n"
            "    condition: null\n"
            "    effects:\n"
            "      - type: mysterious_undefined_effect\n"
            "        foo: bar\n"
        )
        path = tmp_path / "events.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(ValueError, match="mysterious_undefined_effect"):
            load_events_catalog(path=path)


# ---------------------------------------------------------------------------
# Section 3: random events fire at their probability_per_tick rate.
# ---------------------------------------------------------------------------


class TestRandomEventFiringRate:
    """Random events fire at their declared per-tick probability."""

    def test_random_event_with_probability_one_always_fires(self) -> None:
        """Given: a single random event with probability_per_tick=1.0
        When: evaluate_events is called once
        Then: the event fires (prob=1.0 -> always True)."""
        event = Event(
            id=EventId("evt-always"),
            name_ko="항상",
            description_ko="항상 발생하는 이벤트",
            trigger_type="random",
            probability_per_tick=1.0,
            condition=None,
            effects=(),
        )
        state = new_game(42)
        rng = GameRNG(42)
        balance = load_balance()
        new_state, fired, active = evaluate_events(state, rng, balance, [event], [])
        assert [e.id for e in fired] == ["evt-always"]
        assert active == []

    def test_random_event_with_probability_zero_never_fires(self) -> None:
        """Given: a single random event with probability_per_tick=0.0
        When: evaluate_events is called 100 times
        Then: the event never fires."""
        event = Event(
            id=EventId("evt-never"),
            name_ko="절대",
            description_ko="절대 발생하지 않는 이벤트",
            trigger_type="random",
            probability_per_tick=0.0,
            condition=None,
            effects=(),
        )
        state = new_game(42)
        rng = GameRNG(42)
        balance = load_balance()
        fire_count = 0
        for _ in range(100):
            _, fired, _ = evaluate_events(state, rng, balance, [event], [])
            fire_count += len(fired)
        assert fire_count == 0

    def test_random_event_fires_at_expected_rate_with_seed_42(self) -> None:
        """Given: a single random event with probability_per_tick=0.5
        When: evaluate_events is called 10000 times with seed=42
        Then: the event fires within ±500 of 5000 (10% tolerance)."""
        event = Event(
            id=EventId("evt-rate"),
            name_ko="비율",
            description_ko="비율 테스트 이벤트",
            trigger_type="random",
            probability_per_tick=0.5,
            condition=None,
            effects=(),
        )
        state = new_game(42)
        rng = GameRNG(42)
        balance = load_balance()
        fire_count = 0
        for _ in range(10000):
            _, fired, _ = evaluate_events(state, rng, balance, [event], [])
            fire_count += len(fired)
        # Expected 5000; allow ±500 tolerance.
        assert 4500 <= fire_count <= 5500, (
            f"expected ~5000 fires, got {fire_count}"
        )


# ---------------------------------------------------------------------------
# Section 4: conditional events fire ONLY when their condition holds.
# ---------------------------------------------------------------------------


class TestConditionalEventFiring:
    """Conditional events fire only when their condition evaluates True."""

    def test_conditional_event_fires_when_condition_holds(self) -> None:
        """Given: a conditional event whose condition returns True
        When: evaluate_events is called
        Then: the event fires."""
        event = Event(
            id=EventId("evt-cond-yes"),
            name_ko="조건참",
            description_ko="조건이 참일 때 발생",
            trigger_type="conditional",
            probability_per_tick=0.0,
            condition=lambda s, b: True,  # noqa: ARG005 — registered inline
            effects=(),
        )
        state = new_game(42)
        rng = GameRNG(42)
        balance = load_balance()
        _, fired, _ = evaluate_events(state, rng, balance, [event], [])
        assert [e.id for e in fired] == ["evt-cond-yes"]

    def test_conditional_event_skipped_when_condition_false(self) -> None:
        """Given: a conditional event whose condition returns False
        When: evaluate_events is called
        Then: the event does NOT fire."""
        event = Event(
            id=EventId("evt-cond-no"),
            name_ko="조건거짓",
            description_ko="조건이 거짓일 때 발생 안 함",
            trigger_type="conditional",
            probability_per_tick=0.0,
            condition=lambda s, b: False,  # noqa: ARG005
            effects=(),
        )
        state = new_game(42)
        rng = GameRNG(42)
        balance = load_balance()
        _, fired, _ = evaluate_events(state, rng, balance, [event], [])
        assert fired == []


class TestSecretInvestorOfferFires:
    """From the plan QA scenario: secret_investor_offer fires when all_depts_unlocked."""

    def test_secret_investor_offer_fires_when_all_depts_unlocked(self) -> None:
        """Given: a state where every department is unlocked
        When: evaluate_events is called with the catalog
        Then: the secret_investor_offer conditional event fires."""
        catalog = load_events_catalog()
        # Find the secret_investor event by id pattern.
        target = next(
            (e for e in catalog if "secret" in e.id.lower() and e.trigger_type == "conditional"),
            None,
        )
        assert target is not None, "no secret-investor conditional event in catalog"

        # Build a state where every department type is unlocked.
        all_depts = {
            dt.name: _make_dept(did=f"dept-{dt.name}", unlocked=True)
            for dt in DepartmentType
        }
        state = _make_state_with(departments=all_depts)
        rng = GameRNG(42)
        balance = load_balance()

        # Force-evaluate: run a few ticks until target fires (or 1000 attempts).
        fired_target = False
        for _ in range(1000):
            state, fired, _ = evaluate_events(state, rng, balance, catalog, [])
            if any(e.id == target.id for e in fired):
                fired_target = True
                break

        assert fired_target, "secret_investor_offer never fired in 1000 ticks"


# ---------------------------------------------------------------------------
# Section 5: chain depth limit (max 4 levels).
# ---------------------------------------------------------------------------


class TestChainDepthLimit:
    """Chains are truncated at max_concurrent_chain_depth levels."""

    @staticmethod
    def _make_chain_catalog(n: int) -> list[Event]:
        """Build n events chained linearly: evt-1 -> evt-2 -> ... -> evt-n.

        Each event except the last has a ScheduleNextEvent pointing to the
        next event's id. The first event has probability_per_tick=1.0 so it
        always fires; downstream events also have prob=1.0 so chain depth
        is the only limiting factor.
        """
        events: list[Event] = []
        for i in range(1, n + 1):
            effects: tuple[Effect, ...] = ()
            if i < n:
                effects = (
                    ScheduleNextEvent(
                        kind="schedule_next_event",
                        event_id=EventId(f"evt-{i + 1}"),
                    ),
                )
            events.append(
                Event(
                    id=EventId(f"evt-{i}"),
                    name_ko=f"체인 {i}",
                    description_ko=f"체인 이벤트 {i}",
                    trigger_type="random",
                    probability_per_tick=1.0,
                    condition=None,
                    effects=effects,
                )
            )
        return events

    def test_chain_five_deep_truncated_to_four_levels(self) -> None:
        """Given: a 5-event chain (evt-1 chains to evt-2 ... evt-5)
        And: balance.events.max_concurrent_chain_depth = 4
        When: evaluate_events is called with the chain catalog
        Then: exactly 4 events fire (evt-1 .. evt-4); evt-5 is truncated."""
        catalog = self._make_chain_catalog(5)
        state = new_game(42)
        rng = GameRNG(42)
        balance = load_balance()  # max_concurrent_chain_depth = 4

        _, fired, _ = evaluate_events(state, rng, balance, catalog, [])

        fired_ids = [e.id for e in fired]
        assert len(fired_ids) == 4, (
            f"expected 4 levels fired (chain depth=4), got {len(fired_ids)}: {fired_ids}"
        )
        assert fired_ids == ["evt-1", "evt-2", "evt-3", "evt-4"]
        # evt-5 must NOT appear in fired list.
        assert "evt-5" not in fired_ids

    def test_chain_four_deep_all_four_fire(self) -> None:
        """Given: a 4-event chain
        And: max_concurrent_chain_depth = 4
        When: evaluate_events is called
        Then: all 4 events fire (no truncation at the limit)."""
        catalog = self._make_chain_catalog(4)
        state = new_game(42)
        rng = GameRNG(42)
        balance = load_balance()

        _, fired, _ = evaluate_events(state, rng, balance, catalog, [])

        fired_ids = [e.id for e in fired]
        assert fired_ids == ["evt-1", "evt-2", "evt-3", "evt-4"]

    def test_chain_truncation_writes_nothing_for_dropped_follow_up(self) -> None:
        """When a follow-up chain would exceed max depth, the dropped event
        must NOT appear in active_events (truncation means the dropped
        instance is silently discarded, not re-queued)."""
        catalog = self._make_chain_catalog(6)
        state = new_game(42)
        rng = GameRNG(42)
        balance = load_balance()

        _, fired, active = evaluate_events(state, rng, balance, catalog, [])

        active_ids = {inst.event.id for inst in active}
        # evt-5 was truncated; evt-6 never even got scheduled.
        assert "evt-5" not in active_ids
        assert "evt-6" not in active_ids


# ---------------------------------------------------------------------------
# Section 6: condition registry — every registered function works correctly.
# ---------------------------------------------------------------------------


class TestConditionRegistry:
    """The 6 documented conditions in CONDITION_REGISTRY behave correctly."""

    def test_registry_has_required_keys(self) -> None:
        """CONDITION_REGISTRY exposes the 6 documented conditions."""
        required = {
            "all_depts_unlocked",
            "all_employees_skill_max",
            "cash_below_threshold",
            "employee_satisfaction_low",
            "secret_investor_pending",
            "competitor_aggression_high",
        }
        missing = required - CONDITION_REGISTRY.keys()
        assert not missing, f"missing condition keys: {sorted(missing)}"

    def test_all_depts_unlocked_true_when_every_dept_unlocked(self) -> None:
        """all_depts_unlocked: True iff every department.unlocked is True."""
        all_depts = {
            dt.name: _make_dept(did=f"dept-{dt.name}", unlocked=True)
            for dt in DepartmentType
        }
        state = _make_state_with(departments=all_depts)
        assert all_depts_unlocked(state, load_balance()) is True

    def test_all_depts_unlocked_false_when_any_dept_locked(self) -> None:
        """all_depts_unlocked: False if any department.unlocked is False."""
        depts = {
            dt.name: _make_dept(did=f"dept-{dt.name}", unlocked=(dt == DepartmentType.Engineering))
            for dt in DepartmentType
        }
        state = _make_state_with(departments=depts)
        assert all_depts_unlocked(state, load_balance()) is False

    def test_all_depts_unlocked_false_when_no_departments(self) -> None:
        """all_depts_unlocked: False when state has no departments at all."""
        state = _make_state_with()
        assert all_depts_unlocked(state, load_balance()) is False

    def test_all_employees_skill_max_true_when_every_employee_max(self) -> None:
        """all_employees_skill_max: True iff every employee.skill == max_skill (10)."""
        emps = {
            "e1": _make_employee(eid="e1", skill=10),
            "e2": _make_employee(eid="e2", skill=10),
        }
        state = _make_state_with(employees=emps)
        assert all_employees_skill_max(state, load_balance()) is True

    def test_all_employees_skill_max_false_when_one_below_max(self) -> None:
        """all_employees_skill_max: False if any employee.skill < max_skill."""
        emps = {
            "e1": _make_employee(eid="e1", skill=10),
            "e2": _make_employee(eid="e2", skill=9),
        }
        state = _make_state_with(employees=emps)
        assert all_employees_skill_max(state, load_balance()) is False

    def test_all_employees_skill_max_false_when_no_employees(self) -> None:
        """all_employees_skill_max: False when state has no employees."""
        state = _make_state_with()
        assert all_employees_skill_max(state, load_balance()) is False

    def test_cash_below_threshold_true_when_cash_low(self) -> None:
        """cash_below_threshold: True iff company.cash < balance threshold."""
        state = _make_state_with(cash=5_000)
        # Threshold defaults to 10_000 from balance; not yet in yaml — we
        # fall back to the hardcoded default if missing.
        balance = load_balance()
        balance.setdefault("events", {})["cash_low_threshold"] = 10_000
        assert cash_below_threshold(state, balance) is True

    def test_cash_below_threshold_false_when_cash_above_threshold(self) -> None:
        """cash_below_threshold: False iff company.cash >= threshold."""
        state = _make_state_with(cash=50_000)
        balance = load_balance()
        balance.setdefault("events", {})["cash_low_threshold"] = 10_000
        assert cash_below_threshold(state, balance) is False

    def test_employee_satisfaction_low_true_when_any_below_threshold(self) -> None:
        """employee_satisfaction_low: True if any employee.satisfaction below threshold."""
        emps = {
            "e1": _make_employee(eid="e1", satisfaction=80),
            "e2": _make_employee(eid="e2", satisfaction=10),
        }
        state = _make_state_with(employees=emps)
        assert employee_satisfaction_low(state, load_balance()) is True

    def test_employee_satisfaction_low_false_when_all_above(self) -> None:
        """employee_satisfaction_low: False when every employee is happy."""
        emps = {
            "e1": _make_employee(eid="e1", satisfaction=80),
            "e2": _make_employee(eid="e2", satisfaction=50),
        }
        state = _make_state_with(employees=emps)
        assert employee_satisfaction_low(state, load_balance()) is False

    def test_secret_investor_pending_when_cleared_flag_false(self) -> None:
        """secret_investor_pending: True iff state.secret_investor_cleared is False."""
        state = _make_state_with(secret_investor_cleared=False)
        assert secret_investor_pending(state, load_balance()) is True

    def test_secret_investor_pending_when_cleared_flag_true(self) -> None:
        """secret_investor_pending: False iff state.secret_investor_cleared is True."""
        state = _make_state_with(secret_investor_cleared=True)
        assert secret_investor_pending(state, load_balance()) is False

    def test_competitor_aggression_high_true_when_one_above_threshold(self) -> None:
        """competitor_aggression_high: True if any competitor.aggression > threshold."""
        from htop_tycoon.domain.market import Competitor, Market
        from htop_tycoon.domain.state import CompetitorId

        comp = Competitor(
            id=CompetitorId("comp-aggressive"),
            name="Aggressive Co",
            market_share=0.1,
            aggression=0.95,
            cash=50_000,
        )
        market = Market(
            competitors={CompetitorId("comp-aggressive"): comp},
            total_demand_per_week=10_000,
        )
        state = dataclasses.replace(new_game(42), competitors=market.competitors)
        balance = load_balance()
        balance.setdefault("events", {})["competitor_aggression_threshold"] = 0.9
        assert competitor_aggression_high(state, balance) is True

    def test_competitor_aggression_high_false_when_all_below_threshold(self) -> None:
        """competitor_aggression_high: False when every competitor is passive."""
        from htop_tycoon.domain.market import Competitor, Market
        from htop_tycoon.domain.state import CompetitorId

        comp = Competitor(
            id=CompetitorId("comp-passive"),
            name="Passive Co",
            market_share=0.1,
            aggression=0.2,
            cash=50_000,
        )
        market = Market(
            competitors={CompetitorId("comp-passive"): comp},
            total_demand_per_week=10_000,
        )
        state = dataclasses.replace(new_game(42), competitors=market.competitors)
        balance = load_balance()
        balance.setdefault("events", {})["competitor_aggression_threshold"] = 0.9
        assert competitor_aggression_high(state, balance) is False


# ---------------------------------------------------------------------------
# Section 7: condition_registry wiring — yaml condition strings resolve.
# ---------------------------------------------------------------------------


class TestConditionRegistryWiring:
    """The yaml ``condition`` string resolves to a registered callable."""

    def test_yaml_conditions_all_resolve_in_registry(self) -> None:
        """Every condition string in the shipped events.yaml has a matching
        key in CONDITION_REGISTRY (proves the fail-loud guarantee at load
        time)."""
        catalog = load_events_catalog()
        registered = set(CONDITION_REGISTRY.keys())
        for event in catalog:
            if event.trigger_type != "conditional":
                continue
            # event.condition is a callable (resolved at load time), so we
            # cannot inspect the original string. We assert instead that
            # every event has a callable condition (not None) for conditional
            # events.
            assert event.condition is not None, (
                f"conditional event {event.id} has None condition"
            )
            assert callable(event.condition), (
                f"conditional event {event.id} condition is not callable"
            )
        # Also ensure the registered set is non-empty.
        assert registered, "CONDITION_REGISTRY is empty"


# ---------------------------------------------------------------------------
# Section 8: effect application — ShiftMarketShare / BoostRevenue.
# ---------------------------------------------------------------------------


class TestEffectApplication:
    """evaluate_events applies effects to state.products and company."""

    def test_shift_market_share_increases_product_market_share(self) -> None:
        """Given: a product with market_share=0.10
        When: an event with ShiftMarketShare(+0.05) fires
        Then: the product's market_share becomes 0.15."""
        product = _make_product(market_share=0.10)
        event = Event(
            id=EventId("evt-shift"),
            name_ko="시프트",
            description_ko="시장점유율 시프트",
            trigger_type="random",
            probability_per_tick=1.0,
            condition=None,
            effects=(
                ShiftMarketShare(
                    kind="shift_market_share",
                    product_id=ProductId("prod-saas"),
                    delta=0.05,
                ),
            ),
        )
        state = _make_state_with(products={"prod-saas": product})
        rng = GameRNG(42)
        balance = load_balance()

        new_state, fired, _ = evaluate_events(state, rng, balance, [event], [])
        assert fired == [event]
        new_share = new_state.products[ProductId("prod-saas")].market_share
        assert new_share == pytest.approx(0.15)

    def test_shift_market_share_negative_clamps_to_zero(self) -> None:
        """A negative shift that would drive market_share below 0.0 clamps to 0.0."""
        product = _make_product(market_share=0.05)
        event = Event(
            id=EventId("evt-cut"),
            name_ko="컷",
            description_ko="가격 인하",
            trigger_type="random",
            probability_per_tick=1.0,
            condition=None,
            effects=(
                ShiftMarketShare(
                    kind="shift_market_share",
                    product_id=ProductId("prod-saas"),
                    delta=-0.20,
                ),
            ),
        )
        state = _make_state_with(products={"prod-saas": product})
        rng = GameRNG(42)
        balance = load_balance()

        new_state, _, _ = evaluate_events(state, rng, balance, [event], [])
        new_share = new_state.products[ProductId("prod-saas")].market_share
        assert new_share == 0.0

    def test_boost_revenue_increases_revenue_per_week(self) -> None:
        """A BoostRevenue effect increases product.revenue_per_week by its amount."""
        product = _make_product(revenue=1_000)
        event = Event(
            id=EventId("evt-boost"),
            name_ko="부스트",
            description_ko="매출 부스트",
            trigger_type="random",
            probability_per_tick=1.0,
            condition=None,
            effects=(
                BoostRevenue(
                    kind="boost_revenue",
                    product_id=ProductId("prod-saas"),
                    amount=2_500,
                ),
            ),
        )
        state = _make_state_with(products={"prod-saas": product})
        rng = GameRNG(42)
        balance = load_balance()

        new_state, _, _ = evaluate_events(state, rng, balance, [event], [])
        new_rev = new_state.products[ProductId("prod-saas")].revenue_per_week
        assert new_rev == 3_500

    def test_trigger_secret_investor_appends_marker_to_events_active(self) -> None:
        """A TriggerSecretInvestor effect appends a marker to state.events_active."""
        event = Event(
            id=EventId("evt-investor"),
            name_ko="투자자",
            description_ko="비밀 투자자 트리거",
            trigger_type="random",
            probability_per_tick=1.0,
            condition=None,
            effects=(TriggerSecretInvestor(kind="trigger_secret_investor"),),
        )
        state = _make_state_with()
        rng = GameRNG(42)
        balance = load_balance()

        new_state, _, _ = evaluate_events(state, rng, balance, [event], [])
        assert len(new_state.events_active) == 1


# ---------------------------------------------------------------------------
# Section 9: effect union completeness — all 7 effect types parse from YAML.
# ---------------------------------------------------------------------------


class TestEffectUnionParsing:
    """Every effect kind in the Effect union parses from a YAML dict."""

    def _parse_event_with_effect_dict(
        self, tmp_path: Path, effect_dict: dict[str, Any]
    ) -> Event:
        """Write a single-effect YAML and load it."""
        import yaml as _yaml

        yaml_data = {
            "events": [
                {
                    "id": "evt-test",
                    "name_ko": "테스트",
                    "description_ko": "효과 파싱 테스트",
                    "trigger_type": "random",
                    "probability_per_tick": 1.0,
                    "condition": None,
                    "effects": [effect_dict],
                }
            ]
        }
        path = tmp_path / "events.yaml"
        path.write_text(_yaml.safe_dump(yaml_data, allow_unicode=True), encoding="utf-8")
        catalog = load_events_catalog(path=path)
        assert len(catalog) == 1
        return catalog[0]

    def test_parse_shift_market_share(self, tmp_path: Path) -> None:
        event = self._parse_event_with_effect_dict(
            tmp_path,
            {"type": "shift_market_share", "product_id": "SaaS", "delta": 0.1},
        )
        assert isinstance(event.effects[0], ShiftMarketShare)
        assert event.effects[0].product_id == ProductId("SaaS")
        assert event.effects[0].delta == 0.1

    def test_parse_boost_revenue(self, tmp_path: Path) -> None:
        event = self._parse_event_with_effect_dict(
            tmp_path,
            {"type": "boost_revenue", "product_id": "SaaS", "amount": 500},
        )
        assert isinstance(event.effects[0], BoostRevenue)
        assert event.effects[0].amount == 500

    def test_parse_trigger_secret_investor(self, tmp_path: Path) -> None:
        event = self._parse_event_with_effect_dict(
            tmp_path, {"type": "trigger_secret_investor"}
        )
        assert isinstance(event.effects[0], TriggerSecretInvestor)

    def test_parse_schedule_ending(self, tmp_path: Path) -> None:
        event = self._parse_event_with_effect_dict(
            tmp_path, {"type": "schedule_ending", "ending_type": "BANKRUPTCY"}
        )
        assert isinstance(event.effects[0], ScheduleEnding)
        assert event.effects[0].ending_type.value == "BANKRUPTCY"

    def test_parse_schedule_next_event(self, tmp_path: Path) -> None:
        event = self._parse_event_with_effect_dict(
            tmp_path,
            {"type": "schedule_next_event", "event_id": "evt-followup"},
        )
        assert isinstance(event.effects[0], ScheduleNextEvent)
        assert event.effects[0].event_id == EventId("evt-followup")

    def test_parse_add_employee(self, tmp_path: Path) -> None:
        event = self._parse_event_with_effect_dict(
            tmp_path,
            {"type": "add_employee", "dept_id": "dept-eng"},
        )
        assert isinstance(event.effects[0], AddEmployee)
        assert event.effects[0].dept_id == DepartmentId("dept-eng")

    def test_parse_remove_employee(self, tmp_path: Path) -> None:
        event = self._parse_event_with_effect_dict(
            tmp_path,
            {"type": "remove_employee", "employee_id": "emp-001"},
        )
        assert isinstance(event.effects[0], RemoveEmployee)
        assert event.effects[0].employee_id == EmployeeId("emp-001")


# ---------------------------------------------------------------------------
# Section 10: EventInstance is a thin wrapper carrying chain_depth.
# ---------------------------------------------------------------------------


class TestEventInstance:
    """EventInstance wraps an Event with its current chain depth."""

    def test_event_instance_carries_event_and_depth(self) -> None:
        event = Event(
            id=EventId("evt-x"),
            name_ko="X",
            description_ko="X",
            trigger_type="random",
            probability_per_tick=1.0,
            condition=None,
            effects=(),
        )
        inst = EventInstance(event=event, chain_depth=3)
        assert inst.event is event
        assert inst.chain_depth == 3

    def test_event_instance_is_frozen(self) -> None:
        event = Event(
            id=EventId("evt-x"),
            name_ko="X",
            description_ko="X",
            trigger_type="random",
            probability_per_tick=1.0,
            condition=None,
            effects=(),
        )
        inst = EventInstance(event=event, chain_depth=0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            inst.chain_depth = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Section 11: grep guard — event_chain.py does NOT publish via EventBus.
# ---------------------------------------------------------------------------


class TestEventChainPublishGuard:
    """event_chain.py must not import or call event_bus.publish(...)."""

    def test_event_chain_source_does_not_call_publish(self) -> None:
        """Grep guard: no event_bus.publish(...) call in event_chain.py.

        Per AGENTS.md "CRITICAL INVARIANTS": engine functions return
        ``(new_state, events)``; the caller publishes. ``event_chain`` must
        follow the same contract.
        """
        chain_path = (
            Path(__file__).parent.parent
            / "src" / "htop_tycoon" / "engine" / "event_chain.py"
        )
        source = chain_path.read_text(encoding="utf-8")
        # The literal substring "event_bus.publish" must not appear in the source.
        assert "event_bus.publish" not in source, (
            f"event_chain.py must NOT call event_bus.publish(...); "
            f"found it in source. Path: {chain_path}"
        )
        # Also guard against direct publish on a bus variable.
        assert not re.search(r"\bpublish\s*\(", source), (
            "event_chain.py must not call any .publish(...) method; the engine "
            "returns events, callers publish."
        )
        # And ensure the bus class itself is not imported.
        assert "EventBus" not in source, (
            "event_chain.py must not import EventBus; engine functions return events."
        )


# ---------------------------------------------------------------------------
# Section 12: determinism — same seed yields same fire sequence.
# ---------------------------------------------------------------------------


class TestEvaluateEventsDeterminism:
    """evaluate_events is deterministic given a fixed seed."""

    def test_same_seed_same_fires(self) -> None:
        """Two evaluations with the same seed and input produce the same fired list."""
        catalog = load_events_catalog()
        state = _make_state_with()
        rng1 = GameRNG(42)
        rng2 = GameRNG(42)
        balance = load_balance()

        _, fired1, _ = evaluate_events(state, rng1, balance, catalog, [])
        _, fired2, _ = evaluate_events(state, rng2, balance, catalog, [])

        assert [e.id for e in fired1] == [e.id for e in fired2]
