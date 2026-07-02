"""htop-tycoon v3.0 — 100% coverage gate for engine/strategy/ (spec §7.2).

These tests pin the spec §3 strategy manager surface (4 strategies + dispatcher
+ registry) at every line. They are pure-domain tests — no Textual, no I/O, no
clock access — and are the safety net for any future refactor of the strategy
layer.

Conventions:
- Randomness: all RNG flows through ``GameRNG(seed)`` (no bare ``random.*``).
- Domain state: minimal ``GameState`` via ``dataclasses.replace`` patterns.
- Isolation: every test that touches ``StrategyRegistry`` runs under a
  save/restore fixture so the global registry state is invisible to siblings.

Anti-patterns explicitly avoided:
- No ``import random`` outside ``engine/rng.py``.
- No source-code changes — tests only.
- No mocks for the engine actions: they are pure and fast, so call them
  directly to exercise the real dispatch contract.
"""
from __future__ import annotations

from collections.abc import Generator
from types import MappingProxyType

import pytest

from htop_tycoon.domain import (
    Department,
    Employee,
    EmployeeId,
    Event,
    GameProject,
    GameState,
    GenreId,
    JobType,
    Platform,
    PlatformId,
    ProjectId,
    ThemeId,
)
from htop_tycoon.domain.ids import EntityId
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.strategy import (
    AggressiveStrategy,
    BalancedStrategy,
    ConservativeStrategy,
    GenreFocusStrategy,
    dispatch_action,
    get_strategy,
    register_default_strategies,
)
from htop_tycoon.engine.strategy.base import Strategy
from htop_tycoon.engine.strategy.base import StrategyRegistry as _Registry
from htop_tycoon.engine.strategy.types import PlannedAction

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_strategy_registry() -> Generator[None, None, None]:
    """Start each test from a clean registry; restore the session state at end.

    The registry is a class-level dict — without isolation, a test that
    calls ``register_default_strategies()`` would leave 4 entries behind,
    and a sibling test that wants to register a sentinel under the same
    name would fail with a duplicate-name error. Snapshots alone are not
    enough: we must start from empty.
    """
    saved: dict[str, type[Strategy]] = dict(_Registry._registry)
    _Registry._registry.clear()
    try:
        yield
    finally:
        _Registry._registry.clear()
        _Registry._registry.update(saved)


def _emp(
    emp_id: str = "e1",
    *,
    dept: Department = Department.PLANNING,
    job: JobType = JobType.GAME_DESIGNER,
    level: int = 1,
    satisfaction: float = 0.6,
) -> Employee:
    """Minimal valid Employee for GameState construction.

    Default satisfaction (0.6) is above the zombie threshold (0.20) so the
    balanced/conservative fire branches do not trip unless the test says so.
    """
    return Employee(
        id=EmployeeId(emp_id),
        name="테스터",
        dept=dept,
        job=job,
        level=level,
        satisfaction=satisfaction,
    )


def _state(
    *,
    cash: int = 50_000,
    employees: tuple[Employee, ...] = (),
    projects: tuple[GameProject, ...] = (),
    day: int = 0,
) -> GameState:
    """Build a GameState with only the fields the test needs to set."""
    return GameState(
        day=day,
        cash=cash,
        employees=employees,
        projects=projects,
    )


def _project(
    project_id: str = "p1",
    *,
    progress_pct: float = 0.0,
) -> GameProject:
    """Minimal valid GameProject for the assign-path tests."""
    return GameProject(
        id=ProjectId(project_id),
        name="테스트 프로젝트",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=progress_pct,
    )


def _ok_event_status(event: Event) -> str:
    """Pull ``status`` out of an event's MappingProxyType payload.

    Centralized so tests don't repeat the ``payload is not None`` guard.
    """
    assert event.payload is not None
    return str(event.payload["status"])


# ===========================================================================
# engine/strategy/base.py — Strategy ABC + StrategyRegistry
# ===========================================================================


def test_strategy_post_execute_default_noop() -> None:
    """Spec §3.2.2: default ``post_execute`` returns ``None`` and does nothing.

    The default implementation is the ``return None`` line at base.py:40,
    which is the only branch that matters for the default-impl tests.
    """
    strategy = AggressiveStrategy()
    empty_executed: list[PlannedAction] = []
    result: None = strategy.post_execute(_state(), empty_executed)
    assert result is None
    # The state reference is unused but should not be mutated by the no-op.
    state = _state(cash=42)
    strategy.post_execute(state, empty_executed)
    assert state.cash == 42  # no-op confirmed by no side-effect


def test_strategy_registry_register_new() -> None:
    """A fresh name can be registered and immediately looked up."""
    assert "test_custom_strategy" not in _Registry.names()

    class _CustomStrategy(Strategy):
        name = "test_custom_strategy"

        def decide(
            self, state: GameState, rng: GameRNG
        ) -> list[PlannedAction]:
            return []

    _Registry.register("test_custom_strategy", _CustomStrategy)
    assert "test_custom_strategy" in _Registry.names()
    instance = _Registry.get("test_custom_strategy")
    assert isinstance(instance, _CustomStrategy)


def test_strategy_registry_register_duplicate_raises() -> None:
    """Re-registering the same name raises ``ValueError`` (base.py:57)."""
    class _CustomStrategy(Strategy):
        name = "dup_strategy"

        def decide(
            self, state: GameState, rng: GameRNG
        ) -> list[PlannedAction]:
            return []

    _Registry.register("dup_strategy", _CustomStrategy)
    with pytest.raises(ValueError, match="already registered"):
        _Registry.register("dup_strategy", _CustomStrategy)


def test_strategy_registry_unregister_removes_entry() -> None:
    """``unregister`` removes the name from the registry (base.py:62)."""
    class _CustomStrategy(Strategy):
        name = "removable_strategy"

        def decide(
            self, state: GameState, rng: GameRNG
        ) -> list[PlannedAction]:
            return []

    _Registry.register("removable_strategy", _CustomStrategy)
    assert "removable_strategy" in _Registry.names()
    _Registry.unregister("removable_strategy")
    assert "removable_strategy" not in _Registry.names()


def test_strategy_registry_unregister_missing_is_silent() -> None:
    """``unregister`` of an unknown name is a no-op (uses ``pop(..., None)``)."""
    # Should not raise even though "never_registered" was never added.
    _Registry.unregister("never_registered_xyz")
    assert "never_registered_xyz" not in _Registry.names()


def test_strategy_registry_get_unknown_raises() -> None:
    """``get`` of an unregistered name raises ``KeyError`` (base.py:66-71)."""
    with pytest.raises(KeyError, match="strategy not registered"):
        _Registry.get("never_registered_abc")


def test_strategy_registry_names_returns_sorted() -> None:
    """``names`` returns a sorted list of registered strategy names (base.py:75)."""
    class _S(Strategy):
        def __init__(self, tag: str) -> None:
            self._tag = tag
            self.name = f"sort_{tag}"

        def decide(
            self, state: GameState, rng: GameRNG
        ) -> list[PlannedAction]:
            return []

    _Registry.register("sort_c", _S("c"))
    _Registry.register("sort_a", _S("a"))
    _Registry.register("sort_b", _S("b"))

    names = _Registry.names()
    # Sorted alphabetically across all entries present (including any pre-existing).
    assert names == sorted(names)
    # And the three we just added are present in sort order.
    for needle in ("sort_a", "sort_b", "sort_c"):
        assert needle in names


# ===========================================================================
# engine/strategy/aggressive.py — Spec §3.1 row 1
# ===========================================================================


def test_aggressive_decide_with_high_cash_hires() -> None:
    """Aggressive: cash > 30K → queue a HIRE action for planning/game-designer."""
    strategy = AggressiveStrategy()
    state = _state(cash=50_000)  # > 30K threshold
    actions = strategy.decide(state, GameRNG(42))

    hire_actions = [a for a in actions if a.kind == "HIRE"]
    assert len(hire_actions) == 1
    hire = hire_actions[0]
    assert hire.params["dept"] is Department.PLANNING
    assert hire.params["job"] is JobType.GAME_DESIGNER
    assert hire.priority == 70


def test_aggressive_decide_with_low_cash_no_hire() -> None:
    """Aggressive: cash <= 30K → no HIRE action is emitted."""
    strategy = AggressiveStrategy()
    state = _state(cash=30_000)  # threshold is `>`, not `>=`
    actions = strategy.decide(state, GameRNG(42))
    assert not any(a.kind == "HIRE" for a in actions)


def test_aggressive_decide_no_active_project_starts_game() -> None:
    """Aggressive: no active project → queue START_GAME with action/stealth combo."""
    strategy = AggressiveStrategy()
    state = _state(cash=20_000, employees=())  # no active projects
    actions = strategy.decide(state, GameRNG(42))

    start_actions = [a for a in actions if a.kind == "START_GAME"]
    assert len(start_actions) == 1
    start = start_actions[0]
    assert start.params["genre_id"] == "action"
    assert start.params["theme_id"] == "stealth"
    assert start.params["platform_id"] == Platform.PC.name
    assert start.priority == 90


def test_aggressive_decide_with_active_project_no_start() -> None:
    """Aggressive: an active project exists → no START_GAME is queued."""
    strategy = AggressiveStrategy()
    project = _project(progress_pct=42.0)
    state = _state(cash=20_000, projects=(project,))
    actions = strategy.decide(state, GameRNG(42))
    assert not any(a.kind == "START_GAME" for a in actions)


def test_aggressive_decide_actions_sorted_by_priority_desc() -> None:
    """Aggressive: returned list is sorted by priority descending."""
    strategy = AggressiveStrategy()
    state = _state(cash=50_000)  # both HIRE (70) and START_GAME (90) fire
    actions = strategy.decide(state, GameRNG(42))
    priorities = [a.priority for a in actions]
    assert priorities == sorted(priorities, reverse=True)


# ===========================================================================
# engine/strategy/balanced.py — Spec §3.1 row 3
# ===========================================================================


def test_balanced_decide_high_cash_hires() -> None:
    """Balanced: cash > 50K AND <5 employees → queue HIRE (planning/GD)."""
    strategy = BalancedStrategy()
    state = _state(cash=60_000, employees=(_emp(), _emp("e2")))
    actions = strategy.decide(state, GameRNG(42))

    hire_actions = [a for a in actions if a.kind == "HIRE"]
    assert len(hire_actions) == 1
    assert hire_actions[0].params["dept"] is Department.PLANNING
    assert hire_actions[0].params["job"] is JobType.GAME_DESIGNER
    assert hire_actions[0].priority == 70


def test_balanced_decide_low_cash_no_hire() -> None:
    """Balanced: cash <= 50K → no HIRE (threshold is strict `>`)."""
    strategy = BalancedStrategy()
    state = _state(cash=50_000, employees=(_emp(),))
    actions = strategy.decide(state, GameRNG(42))
    assert not any(a.kind == "HIRE" for a in actions)


def test_balanced_decide_fires_underperformers() -> None:
    """Balanced: any employee with satisfaction < 0.10 → FIRE (one per day)."""
    strategy = BalancedStrategy()
    underperformer = _emp("under", satisfaction=0.05)
    high_performer = _emp("good", satisfaction=0.9)
    state = _state(cash=10_000, employees=(underperformer, high_performer))
    actions = strategy.decide(state, GameRNG(42))

    fire_actions = [a for a in actions if a.kind == "FIRE"]
    assert len(fire_actions) == 1  # one fire per day
    assert fire_actions[0].target_id == EntityId("under")
    assert fire_actions[0].params["reason"] == "low_satisfaction"
    assert fire_actions[0].priority == 60


def test_balanced_decide_no_underperformers_no_fire() -> None:
    """Balanced: all employees happy → no FIRE emitted."""
    strategy = BalancedStrategy()
    state = _state(
        cash=10_000,
        employees=(_emp("a", satisfaction=0.5), _emp("b", satisfaction=0.9)),
    )
    actions = strategy.decide(state, GameRNG(42))
    assert not any(a.kind == "FIRE" for a in actions)


def test_balanced_decide_no_active_project_starts() -> None:
    """Balanced: no active project + cash > 20K → START_GAME (rpg/fantasy)."""
    strategy = BalancedStrategy()
    state = _state(cash=25_000)  # no projects, > 20K threshold
    actions = strategy.decide(state, GameRNG(42))

    start_actions = [a for a in actions if a.kind == "START_GAME"]
    assert len(start_actions) == 1
    start = start_actions[0]
    assert start.params["genre_id"] == "rpg"
    assert start.params["theme_id"] == "fantasy"
    assert start.params["platform_id"] == Platform.PC.name
    assert start.priority == 80


def test_balanced_decide_low_cash_no_start() -> None:
    """Balanced: cash <= 20K → no START_GAME even with empty project list."""
    strategy = BalancedStrategy()
    state = _state(cash=20_000)  # threshold is strict `>`
    actions = strategy.decide(state, GameRNG(42))
    assert not any(a.kind == "START_GAME" for a in actions)


# ===========================================================================
# engine/strategy/conservative.py — Spec §3.1 row 2
# ===========================================================================


def test_conservative_decide_very_high_cash_hires() -> None:
    """Conservative: cash > 100K AND <6 employees → HIRE (planning/GD, pri 60)."""
    strategy = ConservativeStrategy()
    state = _state(cash=120_000, employees=(_emp(), _emp("e2")))
    actions = strategy.decide(state, GameRNG(42))

    hire_actions = [a for a in actions if a.kind == "HIRE"]
    assert len(hire_actions) == 1
    assert hire_actions[0].priority == 60
    assert hire_actions[0].params["dept"] is Department.PLANNING
    assert hire_actions[0].params["job"] is JobType.GAME_DESIGNER


def test_conservative_decide_low_cash_no_hire() -> None:
    """Conservative: cash <= 100K → no HIRE (threshold is strict `>`)."""
    strategy = ConservativeStrategy()
    state = _state(cash=100_000, employees=(_emp(),))
    actions = strategy.decide(state, GameRNG(42))
    assert not any(a.kind == "HIRE" for a in actions)


def test_conservative_decide_fires_low_performers() -> None:
    """Conservative: satisfaction < 0.20 → FIRE (one per day, pri 70)."""
    strategy = ConservativeStrategy()
    underperformer = _emp("low_perf", satisfaction=0.15)
    state = _state(cash=10_000, employees=(underperformer,))
    actions = strategy.decide(state, GameRNG(42))

    fire_actions = [a for a in actions if a.kind == "FIRE"]
    assert len(fire_actions) == 1
    assert fire_actions[0].target_id == EntityId("low_perf")
    assert fire_actions[0].priority == 70
    assert fire_actions[0].params["reason"] == "low_satisfaction"


def test_conservative_decide_no_low_performers_no_fire() -> None:
    """Conservative: all satisfaction >= 0.20 → no FIRE emitted."""
    strategy = ConservativeStrategy()
    state = _state(
        cash=10_000,
        employees=(_emp("a", satisfaction=0.5), _emp("b", satisfaction=0.2)),
    )
    actions = strategy.decide(state, GameRNG(42))
    assert not any(a.kind == "FIRE" for a in actions)


def test_conservative_decide_trains_when_no_action() -> None:
    """Conservative: low-level employee + cash > 5K → TRAIN to L2 (one/day)."""
    strategy = ConservativeStrategy()
    newbie = _emp("newbie", level=1)
    state = _state(cash=10_000, employees=(newbie,))
    actions = strategy.decide(state, GameRNG(42))

    train_actions = [a for a in actions if a.kind == "TRAIN"]
    assert len(train_actions) == 1
    assert train_actions[0].target_id == EntityId("newbie")
    assert train_actions[0].params["target_level"] == 2
    assert train_actions[0].priority == 50


def test_conservative_decide_no_active_project_starts() -> None:
    """Conservative: no active project + cash > 50K → START_GAME (sim/modern)."""
    strategy = ConservativeStrategy()
    state = _state(cash=60_000)  # no projects, > 50K threshold
    actions = strategy.decide(state, GameRNG(42))

    start_actions = [a for a in actions if a.kind == "START_GAME"]
    assert len(start_actions) == 1
    start = start_actions[0]
    assert start.params["genre_id"] == "simulation"
    assert start.params["theme_id"] == "modern"
    assert start.params["platform_id"] == Platform.PC.name
    assert start.priority == 80


def test_conservative_decide_no_train_at_or_above_l2() -> None:
    """Conservative: employees at L2+ are not trained (target is L2)."""
    strategy = ConservativeStrategy()
    experienced = _emp("exp", level=2)
    state = _state(cash=10_000, employees=(experienced,))
    actions = strategy.decide(state, GameRNG(42))
    assert not any(a.kind == "TRAIN" for a in actions)


# ===========================================================================
# engine/strategy/genre_focus.py — Spec §3.1 row 4
# ===========================================================================


def test_genre_focus_default_genre() -> None:
    """Default constructor uses the spec §3.1 'action/stealth' pair."""
    strategy = GenreFocusStrategy()
    # Decide on an empty state to see what gets emitted without RNG-driven hires.
    actions = strategy.decide(_state(cash=5_000), GameRNG(42))
    start_actions = [a for a in actions if a.kind == "START_GAME"]
    assert len(start_actions) == 1
    assert start_actions[0].params["genre_id"] == "action"
    assert start_actions[0].params["theme_id"] == "stealth"


def test_genre_focus_override_genre_via_constructor() -> None:
    """Constructor args override the default (genre_focus.py:42-43)."""
    strategy = GenreFocusStrategy(genre_id="rpg", theme_id="fantasy")
    actions = strategy.decide(_state(cash=5_000), GameRNG(42))
    start_actions = [a for a in actions if a.kind == "START_GAME"]
    assert len(start_actions) == 1
    assert start_actions[0].params["genre_id"] == "rpg"
    assert start_actions[0].params["theme_id"] == "fantasy"


def test_genre_focus_high_cash_hires() -> None:
    """Genre Focus: cash > 30K AND <8 employees → HIRE (planning/GD, pri 70)."""
    strategy = GenreFocusStrategy()
    state = _state(cash=40_000, employees=(_emp(),))
    actions = strategy.decide(state, GameRNG(42))

    hire_actions = [a for a in actions if a.kind == "HIRE"]
    assert len(hire_actions) == 1
    assert hire_actions[0].priority == 70
    assert hire_actions[0].params["dept"] is Department.PLANNING
    assert hire_actions[0].params["job"] is JobType.GAME_DESIGNER


def test_genre_focus_low_cash_no_hire() -> None:
    """Genre Focus: cash <= 30K → no HIRE."""
    strategy = GenreFocusStrategy()
    state = _state(cash=30_000, employees=(_emp(),))
    actions = strategy.decide(state, GameRNG(42))
    assert not any(a.kind == "HIRE" for a in actions)


def test_genre_focus_no_active_project_spams_genre() -> None:
    """Genre Focus: always queues a START_GAME (spec §3.1 'continuously')."""
    strategy = GenreFocusStrategy(genre_id="rpg", theme_id="fantasy")
    state = _state(cash=5_000)  # low cash but START_GAME still emits
    actions = strategy.decide(state, GameRNG(42))

    start_actions = [a for a in actions if a.kind == "START_GAME"]
    assert len(start_actions) == 1
    assert start_actions[0].params["genre_id"] == "rpg"
    assert start_actions[0].params["theme_id"] == "fantasy"
    assert start_actions[0].params["platform_id"] == Platform.PC.name
    assert start_actions[0].priority == 80


def test_genre_focus_emits_even_with_active_project() -> None:
    """Genre Focus: emits START_GAME regardless of existing projects (spec §3.1)."""
    strategy = GenreFocusStrategy()
    project = _project(progress_pct=50.0)
    state = _state(cash=5_000, projects=(project,))
    actions = strategy.decide(state, GameRNG(42))
    # Even with an active project, the strategy expresses intent; the engine
    # later rejects with "active_project_exists" but that's the strategy's
    # surface.
    assert any(a.kind == "START_GAME" for a in actions)


# ===========================================================================
# engine/strategy/dispatch.py — ActionKind → engine.actions router
# ===========================================================================


def test_dispatch_hire_success() -> None:
    """HIRE dispatches to engine_actions.hire with dept+job from params."""
    state = _state(cash=50_000)
    action = PlannedAction(
        kind="HIRE",
        params={"dept": Department.PLANNING, "job": JobType.GAME_DESIGNER},
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    assert len(new_state.employees) == 1
    assert new_state.cash == 50_000 - 1_000
    assert events[0].kind == "hire"
    assert _ok_event_status(events[0]) == "ok"


def test_dispatch_fire_with_target_id() -> None:
    """FIRE uses ``action.target_id`` when present (dispatch.py:55-56)."""
    target = _emp("victim")
    state = _state(cash=10_000, employees=(target,))
    action = PlannedAction(
        kind="FIRE",
        target_id=EntityId("victim"),
        params={"reason": "low_satisfaction"},
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    assert len(new_state.employees) == 0
    assert new_state.cash == 10_000 - 500  # FIRE_SEVERANCE
    assert events[0].kind == "fire"
    assert _ok_event_status(events[0]) == "ok"


def test_dispatch_fire_with_employee_id_in_params() -> None:
    """FIRE falls back to ``params["employee_id"]`` when target_id is None."""
    target = _emp("victim2")
    state = _state(cash=10_000, employees=(target,))
    action = PlannedAction(
        kind="FIRE",
        target_id=None,
        params={"employee_id": "victim2", "reason": "strategy"},
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    assert len(new_state.employees) == 0
    assert events[0].kind == "fire"
    assert _ok_event_status(events[0]) == "ok"


def test_dispatch_train() -> None:
    """TRAIN dispatches to engine_actions.train with target_id + level."""
    emp = _emp("learner", level=1)
    state = _state(cash=10_000, employees=(emp,))
    action = PlannedAction(
        kind="TRAIN",
        target_id=EntityId("learner"),
        params={"target_level": 2},
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    updated = next(e for e in new_state.employees if e.id == "learner")
    assert updated.level == 2
    assert events[0].kind == "train"
    assert _ok_event_status(events[0]) == "ok"


def test_dispatch_promote() -> None:
    """PROMOTE dispatches to engine_actions.promote (target_id path).

    Note: ``engine_actions.promote`` delegates to ``train`` internally
    (see engine/actions.py:257), so the success event is emitted with
    ``kind="train"``. The dispatch path itself is what we cover here —
    the dispatcher routes the PROMOTE PlannedAction to the promote entry
    point, and the action's contract is to raise the employee's level by
    one step.
    """
    emp = _emp("rising", level=1)
    state = _state(cash=10_000, employees=(emp,))
    action = PlannedAction(
        kind="PROMOTE",
        target_id=EntityId("rising"),
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    updated = next(e for e in new_state.employees if e.id == "rising")
    assert updated.level == 2
    # promote() delegates to train(); the event kind surfaces as "train".
    assert events[0].kind in ("promote", "train")
    assert _ok_event_status(events[0]) == "ok"


def test_dispatch_demote() -> None:
    """DEMOTE dispatches to engine_actions.demote (target_id path).

    The action returns a structured failure event when the target employee
    is already at level 1 (``"already_at_minimum"``). That is the path we
    exercise here: the dispatch routes DEMOTE to the action, and the action
    emits a failure event without state mutation.
    """
    emp = _emp("grounded", level=1)  # at minimum — demote refuses
    state = _state(cash=10_000, employees=(emp,))
    action = PlannedAction(
        kind="DEMOTE",
        target_id=EntityId("grounded"),
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    # The action returns a failure event; the state is unchanged.
    assert len(events) == 1
    assert events[0].kind == "demote"
    assert _ok_event_status(events[0]) == "failed"
    assert events[0].payload is not None
    assert events[0].payload["reason"] == "already_at_minimum"
    # And the employee is still in the state at the same level.
    assert new_state.employees[0].level == 1


def test_dispatch_demote_unknown_employee() -> None:
    """DEMOTE with an unknown employee id → ``employee_not_found`` failure event.

    Covers the second dispatch branch (employee-not-found path) without
    exercising the action's success branch, which is unreachable in this
    code base due to an unrelated init-field bug in ``engine.actions.demote``.
    The dispatch surface (dispatch.py:70-74) is fully covered by this and
    the previous test combined.
    """
    state = _state(cash=10_000)
    action = PlannedAction(
        kind="DEMOTE",
        target_id=EntityId("ghost"),
        priority=50,
    )
    _new_state, events = dispatch_action(state, GameRNG(42), action)
    assert len(events) == 1
    assert events[0].kind == "demote"
    assert _ok_event_status(events[0]) == "failed"
    assert events[0].payload is not None
    assert events[0].payload["reason"] == "employee_not_found"


def test_dispatch_change_job() -> None:
    """CHANGE_JOB dispatches with new_job from params and target_id from action."""
    emp = _emp("switcher", job=JobType.GAME_DESIGNER)
    state = _state(cash=10_000, employees=(emp,))
    action = PlannedAction(
        kind="CHANGE_JOB",
        target_id=EntityId("switcher"),
        params={"new_job": JobType.PROGRAMMER},
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    updated = next(e for e in new_state.employees if e.id == "switcher")
    assert updated.job is JobType.PROGRAMMER
    assert events[0].kind == "change_job"
    assert _ok_event_status(events[0]) == "ok"


def test_dispatch_start_game() -> None:
    """START_GAME dispatches with genre/theme/platform pulled from params."""
    state = _state(cash=50_000)
    action = PlannedAction(
        kind="START_GAME",
        params={
            "genre_id": "action",
            "theme_id": "stealth",
            "platform_id": Platform.PC.name,
        },
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    assert len(new_state.projects) == 1
    assert events[0].kind == "start_game"
    assert _ok_event_status(events[0]) == "ok"


def test_dispatch_assign_with_target_id() -> None:
    """ASSIGN with target_id: the dispatcher uses target_id for both employee
    and project (per dispatch.py:90-92). Test exercises the ``target is not
    None`` branch by giving both an employee and a project that share the id.
    """
    # Engine.actions.assign compares employee_id==target_id AND project_id==target_id.
    # To get a successful assign with target_id, the state needs an employee and
    # a project whose ids both equal the target.
    emp = _emp("dual")
    project = _project("dual", progress_pct=0.0)
    state = _state(cash=10_000, employees=(emp,), projects=(project,))
    action = PlannedAction(
        kind="ASSIGN",
        target_id=EntityId("dual"),
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    assert events[0].kind == "assign"
    assert _ok_event_status(events[0]) == "ok"
    # And the project picked up the new assignee.
    updated_proj = next(p for p in new_state.projects if p.id == "dual")
    assert "dual" in updated_proj.assignees


def test_dispatch_assign_with_params() -> None:
    """ASSIGN with target_id=None falls back to params for both ids."""
    emp = _emp("worker")
    project = _project("proj-1", progress_pct=0.0)
    state = _state(cash=10_000, employees=(emp,), projects=(project,))
    action = PlannedAction(
        kind="ASSIGN",
        target_id=None,
        params={"employee_id": "worker", "project_id": "proj-1"},
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    assert events[0].kind == "assign"
    assert _ok_event_status(events[0]) == "ok"
    updated_proj = next(p for p in new_state.projects if p.id == "proj-1")
    assert "worker" in updated_proj.assignees


def test_dispatch_nothing() -> None:
    """NOTHING dispatches to engine_actions.nothing → returns (state, [])."""
    state = _state(cash=42_000)
    action = PlannedAction(kind="NOTHING", priority=50)
    new_state, events = dispatch_action(state, GameRNG(42), action)
    assert new_state is state
    assert events == []


def test_dispatch_unknown_action_emits_failure_event() -> None:
    """Unknown ``kind`` → structured failure Event (dispatch.py:97-108).

    The dispatcher does NOT raise; it returns ``(state, [Event])`` with
    ``payload.status == "failed"`` and ``payload.reason == "unknown_action_kind"``.
    """
    state = _state(cash=10_000, day=7)
    # Cast through Any to bypass the ActionKind Literal type-checker; the
    # dispatcher is the *only* code path that needs to handle this case.
    action = PlannedAction(  # type: ignore[arg-type]
        kind="BOGUS",
        priority=50,
    )
    new_state, events = dispatch_action(state, GameRNG(42), action)
    assert new_state is state
    assert len(events) == 1
    event = events[0]
    assert event.kind == "tick"
    assert event.day == 7
    assert event.priority == -50
    assert event.payload is not None
    assert event.payload["status"] == "failed"
    assert event.payload["reason"] == "unknown_action_kind"
    assert event.payload["action_kind"] == "BOGUS"


def test_dispatch_max_actions_per_day_constant_matches_actions_module() -> None:
    """The constant is re-exported from ``engine.actions.MAX_ACTIONS_PER_DAY``.

    Locks the spec §6 contract: dispatcher's day-cap is the same number the
    engine uses for capping strategy loops.
    """
    from htop_tycoon.engine import actions as engine_actions
    from htop_tycoon.engine.strategy.dispatch import MAX_ACTIONS_PER_DAY

    assert MAX_ACTIONS_PER_DAY == engine_actions.MAX_ACTIONS_PER_DAY
    assert MAX_ACTIONS_PER_DAY == 10  # spec §6 default


# ===========================================================================
# engine/strategy/__init__.py — Module-level bootstrap
# ===========================================================================


def test_register_default_strategies_registers_all_four() -> None:
    """After ``register_default_strategies`` the 4 spec §3.1 names are present."""
    # Start from a clean registry state (the fixture restored it before this test).
    register_default_strategies()
    names = _Registry.names()
    for expected in ("aggressive", "balanced", "conservative", "genre_focus"):
        assert expected in names


def test_register_default_strategies_idempotent() -> None:
    """Calling twice does not raise and the registry stays the same size."""
    register_default_strategies()
    size_after_first = len(_Registry._registry)
    register_default_strategies()
    size_after_second = len(_Registry._registry)
    assert size_after_first == size_after_second
    # Each of the 4 defaults is still present and lookup succeeds.
    for name in ("aggressive", "balanced", "conservative", "genre_focus"):
        _Registry.get(name)


def test_get_strategy_returns_instance() -> None:
    """``get_strategy(name)`` returns a fresh Strategy instance (__init__:46)."""
    register_default_strategies()
    strategy = get_strategy("aggressive")
    assert isinstance(strategy, Strategy)
    # Each call returns a fresh instance (the registry's get() instantiates).
    assert strategy is not get_strategy("aggressive")
    # And the instance has the expected name attribute.
    assert strategy.name == "aggressive"


def test_register_default_strategies_does_not_clobber_existing() -> None:
    """If a name is already registered, the bootstrapper skips it.

    Verified by registering a sentinel class under "balanced" first; the
    bootstrapper must not overwrite the entry. ``_Registry.get`` returns
    an *instance* (it calls the class), so we compare with ``isinstance``
    rather than ``is``.
    """
    class _FakeBalanced(Strategy):
        name = "balanced"

        def decide(
            self, state: GameState, rng: GameRNG
        ) -> list[PlannedAction]:
            return []

    _Registry.register("balanced", _FakeBalanced)
    register_default_strategies()
    instance = _Registry.get("balanced")
    assert isinstance(instance, _FakeBalanced)


# ===========================================================================
# Bonus: explicit exercise of the public exports (catches accidental removal)
# ===========================================================================


def test_module_exports_present() -> None:
    """Spot-check that the documented public surface is re-exported."""
    import htop_tycoon.engine.strategy as strategy_mod

    expected: tuple[str, ...] = (
        "ActionKind",
        "AggressiveStrategy",
        "BalancedStrategy",
        "ConservativeStrategy",
        "GenreFocusStrategy",
        "PlannedAction",
        "Strategy",
        "StrategyRegistry",
        "dispatch_action",
        "get_strategy",
        "register_default_strategies",
    )
    for name in expected:
        assert hasattr(strategy_mod, name), f"missing public export: {name}"


def test_planned_action_defaults() -> None:
    """PlannedAction default factory / values match the dataclass definition."""
    action = PlannedAction(kind="NOTHING")
    assert action.target_id is None
    assert action.params == {}
    assert action.priority == 50


def test_planned_action_params_is_independent_per_instance() -> None:
    """``field(default_factory=dict)`` must not share a dict across instances."""
    a = PlannedAction(kind="NOTHING")
    b = PlannedAction(kind="NOTHING")
    a.params["k"] = "v"
    assert b.params == {}


# ---------------------------------------------------------------------------
# Sanity: payload MappingProxyType is preserved through the Event dataclass.
# (No source mutation; the test only documents the existing behavior.)
# ---------------------------------------------------------------------------


def test_event_payload_is_mapping_proxy_type() -> None:
    """Spec §5.3 contract: ``Event.payload`` is wrapped in a MappingProxyType.

    This documents the immutability invariant the engine relies on; the
    strategy dispatcher creates Event objects whose payload is a plain dict
    at construction, but Event.__post_init__ wraps it.
    """
    event = Event(kind="tick", day=0, payload={"status": "ok"})
    assert isinstance(event.payload, MappingProxyType)
    # The contents must still be readable.
    assert event.payload is not None
    assert event.payload["status"] == "ok"


def test_event_payload_default_is_none() -> None:
    """Default payload is None when omitted at construction."""
    event = Event(kind="tick", day=0)
    assert event.payload is None
