"""Tests for T8: Event + Effect union + StoryNode + 5 EndingConditions.

Locks the contract from .omo/plans/htop-tycoon.md line 265-280:
- Event is a frozen dataclass with the documented fields and Effect union.
- Each of the 5 EndingCondition evaluators triggers correctly with crafted fixtures.
- SECRET has 3 sub-conditions: all_depts_unlocked + all_employees_skill==max_skill
  + secret_investor_cleared. The contract uses max_skill (NOT satisfaction).
- TriggerSecretInvestor effect has kind="trigger_secret_investor"; it does NOT
  flip state.secret_investor_cleared. That flip happens ONLY on player resolution.
- StoryNode + Choice are frozen dataclasses with the documented fields.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.ending import (
    BANKRUPTCY,
    HOSTILE_MA,
    IPO,
    SECRET,
    VOLUNTARY_SALE,
    EndingCondition,
    EndingType,
    EvaluationContext,
)
from htop_tycoon.domain.event import (
    AddEmployee,
    BoostRevenue,
    Choice,
    Event,
    RemoveEmployee,
    ScheduleEnding,
    ShiftMarketShare,
    StoryNode,
    TriggerSecretInvestor,
)
from htop_tycoon.domain.state import (
    Company,
    DepartmentId,
    EmployeeId,
    EventId,
    GameState,
    ProductId,
    StoryNodeId,
    new_game,
)

# ============================================================================
# Duck-typed fixtures (T5/T7 are parallel; we don't import their types)
# ============================================================================


class _Dept:
    """Stand-in Department duck-type with only the `unlocked` field SECRET reads."""

    def __init__(self, unlocked: bool) -> None:
        self.unlocked = unlocked


class _Employee:
    """Stand-in Employee duck-type with only the `skill` field SECRET reads."""

    def __init__(self, skill: int) -> None:
        self.skill = skill


class _Competitor:
    """Stand-in Competitor duck-type with cash/aggression/alive fields."""

    def __init__(self, *, cash: int, aggression: float, alive: bool = True) -> None:
        self.cash = cash
        self.aggression = aggression
        self.alive = alive


def _state(
    *,
    cash: int = 0,
    market_cap: int = 0,
    departments: dict[DepartmentId, _Dept] | None = None,
    employees: dict[EmployeeId, _Employee] | None = None,
    competitors: dict[str, _Competitor] | None = None,
    secret_investor_cleared: bool = False,
) -> GameState:
    """Build a GameState with chosen company/collections but fresh game_time."""
    base = new_game(42)
    return dataclasses.replace(
        base,
        company=Company(id="c1", name="Acme", cash=cash, market_cap=market_cap),
        departments=departments or {},
        employees=employees or {},
        competitors=competitors or {},
        secret_investor_cleared=secret_investor_cleared,
    )


# ============================================================================
# EndingType enum (locked contract: exactly 5 values)
# ============================================================================


class TestEndingType:
    def test_exactly_five_members(self) -> None:
        """Given: the locked 5-ending contract
        When: EndingType is inspected
        Then: it has exactly BANKRUPTCY, IPO, HOSTILE_MA, VOLUNTARY_SALE, SECRET
        """
        assert {m.name for m in EndingType} == {
            "BANKRUPTCY",
            "IPO",
            "HOSTILE_MA",
            "VOLUNTARY_SALE",
            "SECRET",
        }

    def test_values_match_names(self) -> None:
        """Each EndingType.value equals its .name (string identity)."""
        for member in EndingType:
            assert member.value == member.name


# ============================================================================
# EvaluationContext (transient; NOT stored on GameState)
# ============================================================================


class TestEvaluationContext:
    def test_default_player_action_is_none(self) -> None:
        """Given: EvaluationContext() with no args
        When: constructed
        Then: player_action defaults to None
        """
        assert EvaluationContext().player_action is None

    def test_explicit_player_action(self) -> None:
        ctx = EvaluationContext(player_action="sell")
        assert ctx.player_action == "sell"

    def test_is_frozen(self) -> None:
        ctx = EvaluationContext()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.player_action = "buy"  # type: ignore[misc]


# ============================================================================
# EndingCondition dataclass shape
# ============================================================================


class TestEndingConditionShape:
    def test_has_ending_type_and_callable_evaluate(self) -> None:
        """Given: a constructed EndingCondition
        When: inspected
        Then: ending_type matches and evaluate is callable
        """
        ec = EndingCondition(EndingType.IPO, lambda s, c: True)
        assert ec.ending_type == EndingType.IPO
        assert callable(ec.evaluate)

    def test_is_frozen(self) -> None:
        ec = EndingCondition(EndingType.IPO, lambda s, c: True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ec.ending_type = EndingType.BANKRUPTCY  # type: ignore[misc]


# ============================================================================
# Concrete EndingCondition instances (5 endings, exactly)
# ============================================================================


class TestEndingInstances:
    def test_five_instances_match_types(self) -> None:
        """Each module-level instance carries the right EndingType."""
        assert BANKRUPTCY.ending_type is EndingType.BANKRUPTCY
        assert IPO.ending_type is EndingType.IPO
        assert HOSTILE_MA.ending_type is EndingType.HOSTILE_MA
        assert VOLUNTARY_SALE.ending_type is EndingType.VOLUNTARY_SALE
        assert SECRET.ending_type is EndingType.SECRET

    def test_all_instances_are_callable(self) -> None:
        """Every EndingCondition.evaluate is callable with (state, ctx)."""
        for ec in (BANKRUPTCY, IPO, HOSTILE_MA, VOLUNTARY_SALE, SECRET):
            assert callable(ec.evaluate)
            # And it can be invoked without raising (any True/False is fine).
            ec.evaluate(_state(), EvaluationContext())  # type: ignore[arg-type]


# ============================================================================
# BANKRUPTCY evaluator
# ============================================================================


class TestBankruptcyEnding:
    def test_triggers_when_cash_below_floor(self) -> None:
        """Given: cash < balance.bankruptcy_cash_floor (-10_000)
        When: BANKRUPTCY.evaluate(state, ctx)
        Then: returns True
        """
        floor = load_balance()["money"]["bankruptcy_cash_floor"]
        state = _state(cash=floor - 1, market_cap=0)
        assert BANKRUPTCY.evaluate(state, EvaluationContext()) is True

    def test_does_not_trigger_at_floor(self) -> None:
        """Strict < (not <=): cash exactly at the floor must NOT trigger."""
        floor = load_balance()["money"]["bankruptcy_cash_floor"]
        state = _state(cash=floor, market_cap=0)
        assert BANKRUPTCY.evaluate(state, EvaluationContext()) is False

    def test_does_not_trigger_when_healthy(self) -> None:
        state = _state(cash=50_000, market_cap=50_000)
        assert BANKRUPTCY.evaluate(state, EvaluationContext()) is False

    def test_does_not_trigger_for_tiny_positive_cash(self) -> None:
        state = _state(cash=1, market_cap=1)
        assert BANKRUPTCY.evaluate(state, EvaluationContext()) is False


# ============================================================================
# IPO evaluator
# ============================================================================


class TestIPOEnding:
    def test_triggers_when_market_cap_at_threshold_and_cash_positive(self) -> None:
        """Given: market_cap >= ipo_market_cap_threshold AND cash > 0
        When: IPO.evaluate
        Then: True
        """
        threshold = load_balance()["endings"]["ipo_market_cap_threshold"]
        state = _state(cash=1, market_cap=threshold)
        assert IPO.evaluate(state, EvaluationContext()) is True

    def test_triggers_when_market_cap_well_above_threshold(self) -> None:
        threshold = load_balance()["endings"]["ipo_market_cap_threshold"]
        state = _state(cash=10_000, market_cap=threshold * 2)
        assert IPO.evaluate(state, EvaluationContext()) is True

    def test_does_not_trigger_when_cash_zero(self) -> None:
        """cash > 0 required (strict)."""
        threshold = load_balance()["endings"]["ipo_market_cap_threshold"]
        state = _state(cash=0, market_cap=threshold * 2)
        assert IPO.evaluate(state, EvaluationContext()) is False

    def test_does_not_trigger_when_cash_negative(self) -> None:
        threshold = load_balance()["endings"]["ipo_market_cap_threshold"]
        state = _state(cash=-100, market_cap=threshold * 2)
        assert IPO.evaluate(state, EvaluationContext()) is False

    def test_does_not_trigger_when_market_cap_below_threshold(self) -> None:
        threshold = load_balance()["endings"]["ipo_market_cap_threshold"]
        state = _state(cash=10_000, market_cap=threshold - 1)
        assert IPO.evaluate(state, EvaluationContext()) is False


# ============================================================================
# HOSTILE_MA evaluator
# ============================================================================


class TestHostileMAEnding:
    def test_triggers_when_alive_competitor_has_more_cash_and_high_aggression(
        self,
    ) -> None:
        """Given: alive competitor with cash >= market_cap AND aggression > threshold
        When: HOSTILE_MA.evaluate
        Then: True
        """
        threshold = load_balance()["endings"]["hostile_ma_trigger_competitor_aggression"]
        state = _state(
            cash=0,
            market_cap=100_000,
            competitors={
                "c1": _Competitor(cash=200_000, aggression=threshold + 0.1),
            },
        )
        assert HOSTILE_MA.evaluate(state, EvaluationContext()) is True

    def test_does_not_trigger_when_competitor_cash_below_market_cap(self) -> None:
        threshold = load_balance()["endings"]["hostile_ma_trigger_competitor_aggression"]
        state = _state(
            cash=0,
            market_cap=100_000,
            competitors={
                "c1": _Competitor(cash=50_000, aggression=threshold + 0.1),
            },
        )
        assert HOSTILE_MA.evaluate(state, EvaluationContext()) is False

    def test_does_not_trigger_when_aggression_at_threshold(self) -> None:
        """Strict > (not >=): aggression exactly at the threshold must NOT trigger."""
        threshold = load_balance()["endings"]["hostile_ma_trigger_competitor_aggression"]
        state = _state(
            cash=0,
            market_cap=100_000,
            competitors={"c1": _Competitor(cash=200_000, aggression=threshold)},
        )
        assert HOSTILE_MA.evaluate(state, EvaluationContext()) is False

    def test_does_not_trigger_when_no_competitors(self) -> None:
        state = _state(cash=0, market_cap=100_000, competitors={})
        assert HOSTILE_MA.evaluate(state, EvaluationContext()) is False

    def test_ignores_dead_competitors(self) -> None:
        """A dead competitor (alive=False) does NOT satisfy the predicate."""
        threshold = load_balance()["endings"]["hostile_ma_trigger_competitor_aggression"]
        state = _state(
            cash=0,
            market_cap=100_000,
            competitors={
                "c1": _Competitor(cash=200_000, aggression=threshold + 0.1, alive=False),
            },
        )
        assert HOSTILE_MA.evaluate(state, EvaluationContext()) is False

    def test_triggers_if_any_one_competitor_meets_criteria(self) -> None:
        """Multiple competitors: any single qualifying one triggers."""
        threshold = load_balance()["endings"]["hostile_ma_trigger_competitor_aggression"]
        state = _state(
            cash=0,
            market_cap=100_000,
            competitors={
                "weak": _Competitor(cash=10_000, aggression=0.5),
                "strong": _Competitor(cash=200_000, aggression=threshold + 0.1),
            },
        )
        assert HOSTILE_MA.evaluate(state, EvaluationContext()) is True


# ============================================================================
# VOLUNTARY_SALE evaluator (uses ctx.player_action)
# ============================================================================


class TestVoluntarySaleEnding:
    def test_triggers_when_sell_action_and_sufficient_cash(self) -> None:
        """Given: ctx.player_action == 'sell' AND cash >= voluntary_sale_min_cash
        When: VOLUNTARY_SALE.evaluate
        Then: True
        """
        min_cash = load_balance()["endings"]["voluntary_sale_min_cash"]
        state = _state(cash=min_cash, market_cap=min_cash)
        ctx = EvaluationContext(player_action="sell")
        assert VOLUNTARY_SALE.evaluate(state, ctx) is True

    def test_does_not_trigger_when_player_action_not_sell(self) -> None:
        min_cash = load_balance()["endings"]["voluntary_sale_min_cash"]
        state = _state(cash=min_cash, market_cap=min_cash)
        ctx = EvaluationContext(player_action="keep")
        assert VOLUNTARY_SALE.evaluate(state, ctx) is False

    def test_does_not_trigger_when_player_action_none(self) -> None:
        """ctx.player_action defaults to None: that does NOT trigger a sale."""
        min_cash = load_balance()["endings"]["voluntary_sale_min_cash"]
        state = _state(cash=min_cash, market_cap=min_cash)
        assert VOLUNTARY_SALE.evaluate(state, EvaluationContext()) is False

    def test_does_not_trigger_when_cash_below_minimum(self) -> None:
        min_cash = load_balance()["endings"]["voluntary_sale_min_cash"]
        state = _state(cash=min_cash - 1, market_cap=min_cash)
        ctx = EvaluationContext(player_action="sell")
        assert VOLUNTARY_SALE.evaluate(state, ctx) is False


# ============================================================================
# SECRET evaluator (3 sub-conditions; uses max_skill, NOT satisfaction)
# ============================================================================


class TestSecretEnding:
    def test_triggers_when_all_three_sub_conditions_met(self) -> None:
        """All depts unlocked AND all employees at max_skill AND secret_investor_cleared."""
        max_skill = load_balance()["employees"]["max_skill"]
        state = _state(
            cash=10_000,
            market_cap=10_000,
            departments={
                DepartmentId("d1"): _Dept(unlocked=True),
                DepartmentId("d2"): _Dept(unlocked=True),
            },
            employees={
                EmployeeId("e1"): _Employee(skill=max_skill),
                EmployeeId("e2"): _Employee(skill=max_skill),
            },
            secret_investor_cleared=True,
        )
        assert SECRET.evaluate(state, EvaluationContext()) is True

    def test_sub_condition_1_false_when_a_department_locked(self) -> None:
        """Sub-condition 1 (all depts unlocked) — fails if any is locked."""
        max_skill = load_balance()["employees"]["max_skill"]
        state = _state(
            cash=10_000,
            market_cap=10_000,
            departments={
                DepartmentId("d1"): _Dept(unlocked=True),
                DepartmentId("d2"): _Dept(unlocked=False),  # locked!
            },
            employees={EmployeeId("e1"): _Employee(skill=max_skill)},
            secret_investor_cleared=True,
        )
        assert SECRET.evaluate(state, EvaluationContext()) is False

    def test_sub_condition_2_false_when_an_employee_below_max_skill(self) -> None:
        """Sub-condition 2 (all employees at max_skill) — fails if any is below."""
        max_skill = load_balance()["employees"]["max_skill"]
        state = _state(
            cash=10_000,
            market_cap=10_000,
            departments={DepartmentId("d1"): _Dept(unlocked=True)},
            employees={
                EmployeeId("e1"): _Employee(skill=max_skill),
                EmployeeId("e2"): _Employee(skill=max_skill - 1),  # below!
            },
            secret_investor_cleared=True,
        )
        assert SECRET.evaluate(state, EvaluationContext()) is False

    def test_sub_condition_3_false_when_secret_investor_not_cleared(self) -> None:
        """Sub-condition 3 (secret_investor_cleared) — fails when False."""
        max_skill = load_balance()["employees"]["max_skill"]
        state = _state(
            cash=10_000,
            market_cap=10_000,
            departments={DepartmentId("d1"): _Dept(unlocked=True)},
            employees={EmployeeId("e1"): _Employee(skill=max_skill)},
            secret_investor_cleared=False,  # not cleared!
        )
        assert SECRET.evaluate(state, EvaluationContext()) is False

    def test_uses_max_skill_not_satisfaction(self) -> None:
        """Contract: SECRET predicate reads employee.skill == max_skill (10).
        Employees with no `satisfaction` attribute at all must still satisfy SECRET
        when their skill equals max_skill.
        """
        max_skill = load_balance()["employees"]["max_skill"]
        assert max_skill == 10
        # _Employee has no `satisfaction` attribute at all.
        emp = _Employee(skill=max_skill)
        assert not hasattr(emp, "satisfaction")
        state = _state(
            cash=10_000,
            market_cap=10_000,
            departments={DepartmentId("d1"): _Dept(unlocked=True)},
            employees={EmployeeId("e1"): emp},
            secret_investor_cleared=True,
        )
        assert SECRET.evaluate(state, EvaluationContext()) is True

    def test_secret_investor_cleared_defaults_false(self) -> None:
        """Sanity: fresh GameState.secret_investor_cleared is False."""
        s = new_game(42)
        assert s.secret_investor_cleared is False

    def test_secret_investor_cleared_flips_only_on_player_resolution(self) -> None:
        """Given: initial state with secret_investor_cleared=False
        When: player accepts the secret-investor offer (resolution) →
              `dataclasses.replace(state, secret_investor_cleared=True)`
        Then: the flag is True.

        And: constructing a TriggerSecretInvestor effect does NOT flip it
        (it's data, not behavior).
        """
        # Given
        s = new_game(42)
        assert s.secret_investor_cleared is False

        # When: player resolves the offer
        resolved = dataclasses.replace(s, secret_investor_cleared=True)

        # Then
        assert resolved.secret_investor_cleared is True

        # And: the effect is just data — it does not mutate state.
        effect = TriggerSecretInvestor(kind="trigger_secret_investor")
        assert effect.kind == "trigger_secret_investor"
        # Effect is frozen & pure-data: simply holding it cannot change state.
        assert s.secret_investor_cleared is False  # unchanged after creating effect


# ============================================================================
# Effect discriminated union — each kind has the correct discriminator + fields
# ============================================================================


class TestEffectDiscriminator:
    def test_add_employee(self) -> None:
        eff = AddEmployee(kind="add_employee", dept_id=DepartmentId("eng"))
        assert eff.kind == "add_employee"
        assert eff.dept_id == "eng"

    def test_remove_employee(self) -> None:
        eff = RemoveEmployee(kind="remove_employee", employee_id=EmployeeId("e1"))
        assert eff.kind == "remove_employee"
        assert eff.employee_id == "e1"

    def test_shift_market_share(self) -> None:
        eff = ShiftMarketShare(
            kind="shift_market_share", product_id=ProductId("SaaS"), delta=0.1
        )
        assert eff.kind == "shift_market_share"
        assert eff.product_id == "SaaS"
        assert eff.delta == 0.1

    def test_boost_revenue(self) -> None:
        eff = BoostRevenue(kind="boost_revenue", product_id=ProductId("SaaS"), amount=5000)
        assert eff.kind == "boost_revenue"
        assert eff.product_id == "SaaS"
        assert eff.amount == 5000

    def test_trigger_secret_investor_kind(self) -> None:
        eff = TriggerSecretInvestor(kind="trigger_secret_investor")
        assert eff.kind == "trigger_secret_investor"

    def test_schedule_ending(self) -> None:
        eff = ScheduleEnding(kind="schedule_ending", ending_type=EndingType.IPO)
        assert eff.kind == "schedule_ending"
        assert eff.ending_type is EndingType.IPO

    def test_each_effect_is_frozen(self) -> None:
        """All Effect subtypes are frozen dataclasses (immutable by design)."""
        samples: tuple[Any, ...] = (
            AddEmployee(kind="add_employee", dept_id=DepartmentId("d")),
            RemoveEmployee(kind="remove_employee", employee_id=EmployeeId("e")),
            ShiftMarketShare(
                kind="shift_market_share", product_id=ProductId("p"), delta=0.0
            ),
            BoostRevenue(kind="boost_revenue", product_id=ProductId("p"), amount=0),
            TriggerSecretInvestor(kind="trigger_secret_investor"),
            ScheduleEnding(kind="schedule_ending", ending_type=EndingType.BANKRUPTCY),
        )
        for eff in samples:
            with pytest.raises(dataclasses.FrozenInstanceError):
                eff.kind = "hacked"  # type: ignore[misc]


# ============================================================================
# Event
# ============================================================================


class TestEvent:
    def _make_event(
        self,
        *,
        condition: Any = None,
        effects: tuple[Any, ...] = (),
        trigger_type: str = "random",
        probability: float = 0.1,
    ) -> Event:
        return Event(
            id=EventId("evt-1"),
            name_ko="테스트 이벤트",
            description_ko="테스트 설명",
            trigger_type=trigger_type,  # type: ignore[arg-type]
            probability_per_tick=probability,
            condition=condition,
            effects=effects,  # type: ignore[arg-type]
        )

    def test_event_has_all_fields(self) -> None:
        """Given: a freshly built Event
        When: fields are read
        Then: each documented field matches the input
        """
        e = self._make_event()
        assert e.id == "evt-1"
        assert e.name_ko == "테스트 이벤트"
        assert e.description_ko == "테스트 설명"
        assert e.trigger_type == "random"
        assert e.probability_per_tick == 0.1
        assert e.condition is None
        assert e.effects == ()

    def test_event_is_frozen(self) -> None:
        e = self._make_event()
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.name_ko = "변경"  # type: ignore[misc]

    def test_event_trigger_type_conditional(self) -> None:
        """trigger_type must accept the 'conditional' literal."""
        e = self._make_event(
            trigger_type="conditional",
            probability=0.0,
            condition=lambda s, c: s.tick >= 10,
        )
        assert e.trigger_type == "conditional"
        assert callable(e.condition)

    def test_event_condition_receives_state_and_ctx(self) -> None:
        """Given: a conditional Event whose condition captures its args
        When: e.condition(state, ctx) is called
        Then: the condition is invoked with (state, ctx) and returns a bool
        """
        calls: list[tuple[Any, Any]] = []

        def cond(state: GameState, ctx: Any) -> bool:
            calls.append((state, ctx))
            return True

        state = new_game(42)
        ctx = EvaluationContext(player_action="sell")
        e = self._make_event(
            trigger_type="conditional", probability=0.0, condition=cond
        )
        assert e.condition is not None
        result = e.condition(state, ctx)
        assert result is True
        assert calls == [(state, ctx)]

    def test_event_holds_effect_tuple(self) -> None:
        """The effects tuple stores Effect instances in order."""
        eff1 = AddEmployee(kind="add_employee", dept_id=DepartmentId("eng"))
        eff2 = TriggerSecretInvestor(kind="trigger_secret_investor")
        e = self._make_event(effects=(eff1, eff2))
        assert len(e.effects) == 2
        assert e.effects[0].kind == "add_employee"
        assert e.effects[1].kind == "trigger_secret_investor"


# ============================================================================
# StoryNode + Choice
# ============================================================================


class TestChoice:
    def test_choice_default_next_node_id_is_none(self) -> None:
        """A Choice with only label_ko defaults next_node_id=None (terminal)."""
        c = Choice(label_ko="예")
        assert c.label_ko == "예"
        assert c.next_node_id is None

    def test_choice_with_explicit_next_node_id(self) -> None:
        c = Choice(label_ko="아니오", next_node_id=StoryNodeId("node-2"))
        assert c.label_ko == "아니오"
        assert c.next_node_id == "node-2"

    def test_choice_is_frozen(self) -> None:
        c = Choice(label_ko="예")
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.label_ko = "아니오"  # type: ignore[misc]


class TestStoryNode:
    def test_story_node_has_all_fields(self) -> None:
        """Given: a StoryNode with 2 choices
        When: fields are inspected
        Then: id/prompt/choices/on_choose match the input
        """

        def on_choose(choice: Choice) -> None:
            return None

        node = StoryNode(
            id=StoryNodeId("node-1"),
            prompt_ko="선택지",
            choices=(
                Choice(label_ko="예"),
                Choice(label_ko="아니오", next_node_id=StoryNodeId("node-2")),
            ),
            on_choose=on_choose,
        )
        assert node.id == "node-1"
        assert node.prompt_ko == "선택지"
        assert len(node.choices) == 2
        assert node.choices[0].label_ko == "예"
        assert node.choices[0].next_node_id is None
        assert node.choices[1].next_node_id == "node-2"
        assert node.on_choose is on_choose

    def test_story_node_is_frozen(self) -> None:
        node = StoryNode(
            id=StoryNodeId("node-1"),
            prompt_ko="x",
            choices=(),
            on_choose=lambda c: None,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.prompt_ko = "변경"  # type: ignore[misc]

    def test_story_node_on_choose_callable(self) -> None:
        """on_choose is invoked with a Choice and returns something."""

        def handler(choice: Choice) -> str:
            return f"chose:{choice.label_ko}"

        node = StoryNode(
            id=StoryNodeId("node-1"),
            prompt_ko="x",
            choices=(Choice(label_ko="A"), Choice(label_ko="B")),
            on_choose=handler,
        )
        assert node.on_choose(node.choices[0]) == "chose:A"
        assert node.on_choose(node.choices[1]) == "chose:B"
