"""Tests for T15: engine-level ending evaluation, apply_ending, story branch resolver.

Locks the contract from .omo/plans/htop-tycoon.md line 415-432:

- ``evaluate_endings`` checks the 5 endings in EXACT priority order
  (BANKRUPTCY > HOSTILE_MA > VOLUNTARY_SALE > IPO > SECRET) and returns
  the FIRST triggered ending (or None).
- ``apply_ending(state, ending_type)`` appends a marker to
  ``state.ending_history`` (via dataclasses.replace) and returns the
  ``[EndingTriggered(ending_type)]`` event. It does NOT mutate input state
  and does NOT clear it (state preserved for the T21 review screen).
- ``resolve_story_branch(state, story_node_id, chosen_option, story_nodes)``
  applies the chosen option's effects from the StoryNode catalog.
- ``evaluate_endings`` never auto-triggers VOLUNTARY_SALE without
  ``player_action="sell"``.
- Engine module does NOT call ``event_bus.publish(...)`` from within
  ``apply_ending`` (events are returned, not published).
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.ending import (
    EndingType,
)
from htop_tycoon.domain.event import Choice, StoryNode
from htop_tycoon.domain.state import (
    Company,
    DepartmentId,
    EmployeeId,
    GameState,
    StoryNodeId,
    new_game,
)
from htop_tycoon.engine.ending import (
    apply_ending,
    evaluate_endings,
    resolve_story_branch,
)
from htop_tycoon.engine.events import EndingTriggered

# ============================================================================
# Duck-typed fixtures — T15 re-uses the same patterns as test_event_ending.py
# so the tests do not depend on the concrete Department/Employee/Competitor
# dataclasses (those are owned by T5/T7).
# ============================================================================


class _Dept:
    """Stand-in Department duck-type; only `unlocked` is read by SECRET."""

    def __init__(self, unlocked: bool) -> None:
        self.unlocked = unlocked


class _Employee:
    """Stand-in Employee duck-type; only `skill` is read by SECRET."""

    def __init__(self, skill: int) -> None:
        self.skill = skill


class _Competitor:
    """Stand-in Competitor duck-type; cash/aggression/alive read by HOSTILE_MA."""

    def __init__(self, *, cash: int, aggression: float, alive: bool = True) -> None:
        self.cash = cash
        self.aggression = aggression
        self.alive = alive


def _state(
    *,
    cash: int = 50_000,
    market_cap: int = 50_000,
    departments: dict[DepartmentId, _Dept] | None = None,
    employees: dict[EmployeeId, _Employee] | None = None,
    competitors: dict[str, _Competitor] | None = None,
    secret_investor_cleared: bool = False,
    ending_history: list | None = None,
) -> GameState:
    """Build a GameState with chosen collections and fresh game_time."""
    base = new_game(42)
    return dataclasses.replace(
        base,
        company=Company(id="c1", name="Acme", cash=cash, market_cap=market_cap),
        departments=departments or {},
        employees=employees or {},
        competitors=competitors or {},
        secret_investor_cleared=secret_investor_cleared,
        ending_history=list(ending_history) if ending_history is not None else [],
    )


_BALANCE: dict = load_balance()


# ============================================================================
# evaluate_endings — priority order (LOCKED)
# ============================================================================


class TestEvaluateEndingsPriorityOrder:
    def test_priority_order_constant_is_locked(self) -> None:
        """Locked priority order: BANKRUPTCY > HOSTILE_MA > VOLUNTARY_SALE > IPO > SECRET.

        Guards against accidental reordering. Re-prioritization requires
        updating the plan (T15, T8, T33) first.
        """
        from htop_tycoon.engine.ending import PRIORITY_ORDER

        expected = (
            EndingType.BANKRUPTCY,
            EndingType.HOSTILE_MA,
            EndingType.VOLUNTARY_SALE,
            EndingType.IPO,
            EndingType.SECRET,
        )
        assert tuple(condition.ending_type for condition in PRIORITY_ORDER) == expected

    def test_returns_none_when_no_ending_triggers(self) -> None:
        """A healthy state with no conditions met returns None."""
        state = _state(cash=50_000, market_cap=50_000)
        assert evaluate_endings(state, _BALANCE) is None

    def test_bankruptcy_triggers_first_in_priority(self) -> None:
        """Given: state with cash below bankruptcy floor AND high market cap (would trigger IPO)
        When: evaluate_endings
        Then: BANKRUPTCY wins (higher priority).
        """
        ipo_threshold = load_balance()["endings"]["ipo_market_cap_threshold"]
        floor = load_balance()["money"]["bankruptcy_cash_floor"]
        state = _state(cash=floor - 1, market_cap=ipo_threshold * 2)
        assert evaluate_endings(state, _BALANCE) is EndingType.BANKRUPTCY

    def test_hostile_ma_wins_over_ipo_when_bankruptcy_clear(self) -> None:
        """Given: cash is fine (no bankruptcy), hostile_ma condition holds, AND market_cap
        is high (would trigger IPO)
        When: evaluate_endings
        Then: HOSTILE_MA wins (priority over IPO).
        """
        ipo_threshold = load_balance()["endings"]["ipo_market_cap_threshold"]
        ma_threshold = load_balance()["endings"]["hostile_ma_trigger_competitor_aggression"]
        state = _state(
            cash=10_000,
            market_cap=ipo_threshold * 2,
            competitors={
                "c1": _Competitor(cash=ipo_threshold * 2 + 1, aggression=ma_threshold + 0.1),
            },
        )
        assert evaluate_endings(state, _BALANCE) is EndingType.HOSTILE_MA

    def test_voluntary_sale_wins_over_ipo_when_sell_action_set(self) -> None:
        """Given: cash >= voluntary_sale_min AND market_cap >= ipo threshold AND player_action=sell
        When: evaluate_endings(state, _BALANCE, player_action="sell")
        Then: VOLUNTARY_SALE wins (priority over IPO).
        """
        ipo_threshold = load_balance()["endings"]["ipo_market_cap_threshold"]
        min_cash = load_balance()["endings"]["voluntary_sale_min_cash"]
        state = _state(cash=max(min_cash, ipo_threshold // 100) + 1000, market_cap=ipo_threshold)
        result = evaluate_endings(state, _BALANCE, player_action="sell")
        assert result is EndingType.VOLUNTARY_SALE

    def test_ipo_wins_over_secret(self) -> None:
        """Given: SECRET conditions AND IPO conditions both hold
        When: evaluate_endings
        Then: IPO wins (priority over SECRET).
        """
        balance = load_balance()
        ipo_threshold = int(balance["endings"]["ipo_market_cap_threshold"])
        max_skill = int(balance["employees"]["max_skill"])

        state = _state(
            cash=1,  # IPO requires cash > 0
            market_cap=ipo_threshold,
            departments={
                DepartmentId("d1"): _Dept(unlocked=True),
                DepartmentId("d2"): _Dept(unlocked=True),
                DepartmentId("d3"): _Dept(unlocked=True),
                DepartmentId("d4"): _Dept(unlocked=True),
                DepartmentId("d5"): _Dept(unlocked=True),
            },
            employees={
                EmployeeId("e1"): _Employee(skill=max_skill),
            },
            secret_investor_cleared=True,
        )
        assert evaluate_endings(state, _BALANCE) is EndingType.IPO

    def test_secret_fires_when_alone(self) -> None:
        """Given: only SECRET conditions hold (no other ending triggers)
        When: evaluate_endings
        Then: SECRET.
        """
        balance = load_balance()
        max_skill = int(balance["employees"]["max_skill"])

        state = _state(
            cash=50_000,
            market_cap=50_000,
            departments={
                DepartmentId("d1"): _Dept(unlocked=True),
                DepartmentId("d2"): _Dept(unlocked=True),
                DepartmentId("d3"): _Dept(unlocked=True),
                DepartmentId("d4"): _Dept(unlocked=True),
                DepartmentId("d5"): _Dept(unlocked=True),
            },
            employees={
                EmployeeId("e1"): _Employee(skill=max_skill),
            },
            secret_investor_cleared=True,
        )
        assert evaluate_endings(state, _BALANCE) is EndingType.SECRET


# ============================================================================
# evaluate_endings — individual ending coverage (all 5 endings must trigger)
# ============================================================================


class TestAllFiveEndingsTrigger:
    def test_bankruptcy_triggers(self) -> None:
        """cash < bankruptcy_cash_floor -> BANKRUPTCY."""
        floor = load_balance()["money"]["bankruptcy_cash_floor"]
        state = _state(cash=floor - 1, market_cap=0)
        assert evaluate_endings(state, _BALANCE) is EndingType.BANKRUPTCY

    def test_hostile_ma_triggers(self) -> None:
        """An alive competitor with cash>=market_cap AND aggression>threshold -> HOSTILE_MA."""
        balance = load_balance()
        ma_threshold = float(balance["endings"]["hostile_ma_trigger_competitor_aggression"])
        state = _state(
            cash=0,
            market_cap=100_000,
            competitors={
                "c1": _Competitor(cash=200_000, aggression=ma_threshold + 0.1),
            },
        )
        assert evaluate_endings(state, _BALANCE) is EndingType.HOSTILE_MA

    def test_voluntary_sale_triggers_when_player_action_sell(self) -> None:
        """player_action='sell' AND cash >= voluntary_sale_min_cash -> VOLUNTARY_SALE."""
        min_cash = load_balance()["endings"]["voluntary_sale_min_cash"]
        state = _state(cash=min_cash + 1, market_cap=min_cash + 1)
        assert evaluate_endings(state, _BALANCE, player_action="sell") is EndingType.VOLUNTARY_SALE

    def test_ipo_triggers(self) -> None:
        """market_cap >= ipo_market_cap_threshold AND cash > 0 -> IPO."""
        threshold = load_balance()["endings"]["ipo_market_cap_threshold"]
        state = _state(cash=1, market_cap=threshold)
        assert evaluate_endings(state, _BALANCE) is EndingType.IPO

    def test_secret_triggers(self) -> None:
        """All 3 SECRET sub-conditions hold -> SECRET."""
        balance = load_balance()
        max_skill = int(balance["employees"]["max_skill"])
        state = _state(
            cash=50_000,
            market_cap=50_000,
            departments={
                DepartmentId("d1"): _Dept(unlocked=True),
                DepartmentId("d2"): _Dept(unlocked=True),
                DepartmentId("d3"): _Dept(unlocked=True),
                DepartmentId("d4"): _Dept(unlocked=True),
                DepartmentId("d5"): _Dept(unlocked=True),
            },
            employees={
                EmployeeId("e1"): _Employee(skill=max_skill),
            },
            secret_investor_cleared=True,
        )
        assert evaluate_endings(state, _BALANCE) is EndingType.SECRET


# ============================================================================
# VOLUNTARY_SALE — player_action="sell" is REQUIRED (the only action-required ending)
# ============================================================================


class TestVoluntarySaleRequiresPlayerAction:
    def test_voluntary_sale_does_not_trigger_without_sell(self) -> None:
        """Given: cash >= voluntary_sale_min_cash but player_action is None
        When: evaluate_endings(state, _BALANCE)  # default player_action=None
        Then: VOLUNTARY_SALE must NOT trigger; evaluation returns None (or another
              higher-priority ending, but never VOLUNTARY_SALE here).
        """
        min_cash = load_balance()["endings"]["voluntary_sale_min_cash"]
        state = _state(cash=min_cash + 100, market_cap=min_cash + 100)
        result = evaluate_endings(state, _BALANCE)
        assert result is not EndingType.VOLUNTARY_SALE

    def test_voluntary_sale_does_not_trigger_with_other_player_action(self) -> None:
        """Given: cash >= voluntary_sale_min_cash but player_action='buy'
        When: evaluate_endings(state, _BALANCE, player_action='buy')
        Then: VOLUNTARY_SALE must NOT trigger.
        """
        min_cash = load_balance()["endings"]["voluntary_sale_min_cash"]
        state = _state(cash=min_cash + 100, market_cap=min_cash + 100)
        result = evaluate_endings(state, _BALANCE, player_action="buy")
        assert result is not EndingType.VOLUNTARY_SALE

    def test_voluntary_sale_triggers_only_with_sell(self) -> None:
        """player_action='sell' is the unique trigger for VOLUNTARY_SALE."""
        min_cash = load_balance()["endings"]["voluntary_sale_min_cash"]
        state = _state(cash=min_cash + 100, market_cap=min_cash + 100)
        assert evaluate_endings(state, _BALANCE, player_action="sell") is EndingType.VOLUNTARY_SALE


# ============================================================================
# SECRET — each of the 3 sub-conditions is required (must NOT trigger if any unmet)
# ============================================================================


class TestSecretRequiresAllThreeSubConditions:
    def test_secret_does_not_trigger_when_a_dept_locked(self) -> None:
        """SECRET requires all departments unlocked. With one dept locked, no SECRET."""
        balance = load_balance()
        max_skill = int(balance["employees"]["max_skill"])
        state = _state(
            cash=50_000,
            market_cap=50_000,
            departments={
                DepartmentId("d1"): _Dept(unlocked=True),
                DepartmentId("d2"): _Dept(unlocked=True),
                DepartmentId("d3"): _Dept(unlocked=True),
                DepartmentId("d4"): _Dept(unlocked=True),
                DepartmentId("d5"): _Dept(unlocked=False),  # one locked
            },
            employees={EmployeeId("e1"): _Employee(skill=max_skill)},
            secret_investor_cleared=True,
        )
        assert evaluate_endings(state, _BALANCE) is not EndingType.SECRET

    def test_secret_does_not_trigger_when_employee_skill_below_max(self) -> None:
        """SECRET requires all employees at max_skill. With one below, no SECRET."""
        balance = load_balance()
        max_skill = int(balance["employees"]["max_skill"])
        state = _state(
            cash=50_000,
            market_cap=50_000,
            departments={
                DepartmentId("d1"): _Dept(unlocked=True),
                DepartmentId("d2"): _Dept(unlocked=True),
                DepartmentId("d3"): _Dept(unlocked=True),
                DepartmentId("d4"): _Dept(unlocked=True),
                DepartmentId("d5"): _Dept(unlocked=True),
            },
            employees={
                EmployeeId("e1"): _Employee(skill=max_skill),
                EmployeeId("e2"): _Employee(skill=max_skill - 1),  # one below
            },
            secret_investor_cleared=True,
        )
        assert evaluate_endings(state, _BALANCE) is not EndingType.SECRET

    def test_secret_does_not_trigger_when_secret_investor_not_cleared(self) -> None:
        """SECRET requires secret_investor_cleared=True. When False, no SECRET."""
        balance = load_balance()
        max_skill = int(balance["employees"]["max_skill"])
        state = _state(
            cash=50_000,
            market_cap=50_000,
            departments={
                DepartmentId("d1"): _Dept(unlocked=True),
                DepartmentId("d2"): _Dept(unlocked=True),
                DepartmentId("d3"): _Dept(unlocked=True),
                DepartmentId("d4"): _Dept(unlocked=True),
                DepartmentId("d5"): _Dept(unlocked=True),
            },
            employees={EmployeeId("e1"): _Employee(skill=max_skill)},
            secret_investor_cleared=False,  # not cleared
        )
        assert evaluate_endings(state, _BALANCE) is not EndingType.SECRET

    def test_secret_does_not_trigger_with_empty_collections(self) -> None:
        """Edge case: empty departments dict -> SECRET cannot fire (vacuous truth).

        With an empty dict, ``all(dept.unlocked for dept in {}.values())`` is True,
        but with an empty employees dict the ``all(...) == max_skill`` is also
        vacuously True. The discriminator MUST be secret_investor_cleared
        (False in this fixture) so SECRET still does NOT fire.
        """
        state = _state(
            cash=50_000,
            market_cap=50_000,
            departments={},
            employees={},
            secret_investor_cleared=False,
        )
        assert evaluate_endings(state, _BALANCE) is not EndingType.SECRET


# ============================================================================
# apply_ending — appends to ending_history, returns EndingTriggered event
# ============================================================================


class TestApplyEnding:
    def test_apply_ending_returns_ending_triggered_event(self) -> None:
        """apply_ending returns [EndingTriggered(ending_type)] as the only event."""
        state = _state()
        new_state, events = apply_ending(state, EndingType.IPO)
        assert len(events) == 1
        assert isinstance(events[0], EndingTriggered)
        assert events[0].ending_type is EndingType.IPO

    def test_apply_ending_appends_to_ending_history(self) -> None:
        """The returned state has one more entry in ending_history."""
        state = _state(ending_history=[])
        new_state, _ = apply_ending(state, EndingType.BANKRUPTCY)
        assert len(new_state.ending_history) == 1

    def test_apply_ending_preserves_existing_history(self) -> None:
        """Existing markers are preserved; new one is appended (not replaced)."""
        state = _state(ending_history=[{"kind": "schedule_ending", "ending_type": "IPO"}])
        new_state, _ = apply_ending(state, EndingType.BANKRUPTCY)
        assert len(new_state.ending_history) == 2
        # First element is the original marker (preserved).
        assert new_state.ending_history[0] == {
            "kind": "schedule_ending",
            "ending_type": "IPO",
        }

    def test_apply_ending_does_not_mutate_input_state(self) -> None:
        """The input GameState is unchanged (apply_ending uses dataclasses.replace)."""
        state = _state(ending_history=[])
        original_history_len = len(state.ending_history)
        new_state, _ = apply_ending(state, EndingType.BANKRUPTCY)
        assert len(state.ending_history) == original_history_len
        assert state is not new_state
        assert state.ending_history == []  # input unaffected

    def test_apply_ending_preserves_state_for_review_screen(self) -> None:
        """apply_ending does NOT clear the game state (cash/depts/employees preserved).

        The ending screen (T21) needs the full state to show a review summary.
        """
        state = _state(
            cash=123_456,
            market_cap=789_012,
            departments={DepartmentId("d1"): _Dept(unlocked=True)},
            employees={EmployeeId("e1"): _Employee(skill=7)},
        )
        new_state, _ = apply_ending(state, EndingType.IPO)
        assert new_state.company.cash == 123_456
        assert new_state.company.market_cap == 789_012
        assert DepartmentId("d1") in new_state.departments
        assert EmployeeId("e1") in new_state.employees

    def test_apply_ending_with_each_of_five_endings(self) -> None:
        """apply_ending works for all 5 ending types (uniform behavior)."""
        for ending in EndingType:
            state = _state()
            new_state, events = apply_ending(state, ending)
            assert events[0].ending_type is ending
            assert len(new_state.ending_history) == 1


# ============================================================================
# resolve_story_branch — applies the chosen StoryNode's chosen option
# ============================================================================


class TestResolveStoryBranch:
    def test_resolve_story_branch_invokes_on_choose(self) -> None:
        """``on_choose`` is invoked with the picked Choice and the state is returned."""
        chosen_option_idx = 0
        node_id = StoryNodeId("node-1")

        seen: list[Choice] = []

        def on_choose(choice: Choice) -> None:
            seen.append(choice)

        node = StoryNode(
            id=node_id,
            prompt_ko="테스트 노드",
            choices=(
                Choice(label_ko="선택 1", next_node_id=None),
                Choice(label_ko="선택 2", next_node_id=None),
            ),
            on_choose=on_choose,
        )
        story_nodes = {node_id: node}

        state = _state()
        # The resolver currently does not modify state; it just invokes the
        # callback and returns the state unchanged. (We lock that contract.)
        result = resolve_story_branch(state, node_id, chosen_option_idx, story_nodes)
        assert result is state
        assert len(seen) == 1
        assert seen[0].label_ko == "선택 1"

    def test_resolve_story_branch_unknown_node_raises(self) -> None:
        """Unknown story_node_id must raise (fail-loud, no silent no-op)."""
        story_nodes: dict[StoryNodeId, StoryNode] = {}
        with pytest.raises(KeyError):
            resolve_story_branch(_state(), StoryNodeId("missing"), 0, story_nodes)

    def test_resolve_story_branch_out_of_range_option_raises(self) -> None:
        """chosen_option beyond the choice tuple must raise."""
        node_id = StoryNodeId("node-1")
        node = StoryNode(
            id=node_id,
            prompt_ko="테스트 노드",
            choices=(Choice(label_ko="선택 1", next_node_id=None),),
            on_choose=lambda _c: None,
        )
        with pytest.raises(IndexError):
            resolve_story_branch(_state(), node_id, 5, {node_id: node})

    def test_resolve_story_branch_does_not_mutate_input_state(self) -> None:
        """resolve_story_branch does not mutate input state."""
        node_id = StoryNodeId("node-1")
        node = StoryNode(
            id=node_id,
            prompt_ko="테스트 노드",
            choices=(Choice(label_ko="선택 1", next_node_id=None),),
            on_choose=lambda _c: None,
        )
        state = _state(cash=99_999)
        result = resolve_story_branch(state, node_id, 0, {node_id: node})
        assert result.company.cash == 99_999
        assert result is state


# ============================================================================
# Anti-pattern guard: NO event_bus.publish call in engine/ending.py
# ============================================================================


class TestEngineEndingModuleGuardrails:
    def test_engine_ending_does_not_call_event_bus_publish(self) -> None:
        """The locked invariant: engine functions return events, never publish.

        No ``event_bus.publish(...)`` call is allowed inside
        ``src/htop_tycoon/engine/ending.py``.
        """
        module_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "htop_tycoon"
            / "engine"
            / "ending.py"
        )
        source = module_path.read_text(encoding="utf-8")
        match = re.search(r"\bevent_bus\.publish\s*\(", source)
        assert match is None, (
            f"engine/ending.py must NOT call event_bus.publish(...); found at "
            f"offset {match.start() if match else 'n/a'}. Events are returned "
            f"in the tuple, not published."
        )

    def test_engine_ending_does_not_import_event_bus(self) -> None:
        """Defense-in-depth: EventBus should not be imported here either.

        Since the module has no business publishing events, importing the
        EventBus would be a smell. If a future change genuinely needs the
        bus, this guard must be reviewed.
        """
        module_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "htop_tycoon"
            / "engine"
            / "ending.py"
        )
        source = module_path.read_text(encoding="utf-8")
        assert "EventBus" not in source, (
            "engine/ending.py must NOT reference the EventBus; events are returned "
            "in the tuple, not published. Remove the import."
        )


# ============================================================================
# Sanity: the engine module re-exports (or imports) the public surface
# ============================================================================


class TestEngineEndingPublicSurface:
    def test_evaluate_endings_signature(self) -> None:
        """The signature is ``evaluate_endings(state, balance, player_action=None)``.

        ``state`` and ``balance`` are required positional arguments; only
        ``player_action`` has a default (None). This matches the task spec
        and the ``evaluate_events(state, rng, balance, ...)`` convention
        used by T14.
        """
        import inspect

        sig = inspect.signature(evaluate_endings)
        assert "state" in sig.parameters
        assert "balance" in sig.parameters
        assert "player_action" in sig.parameters
        assert sig.parameters["player_action"].default is None
        assert sig.parameters["state"].default is inspect.Parameter.empty
        assert sig.parameters["balance"].default is inspect.Parameter.empty
        evaluate_endings(_state(), load_balance())
