"""Phase 2H: Strategy module — ABC + 4 strategies + dispatch."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Department,
    Employee,
    EmployeeId,
    Genre,
    Job,
    Money,
)
from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine.strategy import (
    STRATEGY_REGISTRY,
    AggressiveStrategy,
    BalancedStrategy,
    ConservativeStrategy,
    GenreFocusStrategy,
    Strategy,
    current_strategy,
)
from htop_tycoon.engine.strategy.types import StrategyDecision


def test_strategy_abc_cannot_instantiate() -> None:
    import pytest

    with pytest.raises(TypeError):
        Strategy()  # type: ignore[abstract]


def test_aggressive_hires_when_rich_and_understaffed() -> None:
    state = CompanyState(cash=Money(60_000_00))
    for i in range(1, 4):
        state = state.add_employee(
            Employee(
                id=EmployeeId(i),
                name=f"Emp{i}",
                job=Job.JUNIOR,
                level=1,
                salary=Money(200_00),
                satisfaction=80,
                dept=Department.DEV,
            )
        )
    strat = AggressiveStrategy()
    decisions = strat.decide(state, GameRng(0))
    assert any(d.action == "hire" and d.magnitude == 2 for d in decisions)


def test_aggressive_starts_project_when_none_active() -> None:
    state = CompanyState(cash=Money(50_000_00))
    strat = AggressiveStrategy()
    decisions = strat.decide(state, GameRng(0))
    assert any(d.action == "start_project" for d in decisions)


def test_aggressive_no_actions_when_fully_staffed_with_projects() -> None:
    from htop_tycoon.domain import (
        GameProject,
        GameTitle,
        Platform,
        Progress,
        ProjectId,
        QualityAxes,
    )

    state = CompanyState(cash=Money(200_000_00))
    for i in range(1, 10):
        state = state.add_employee(
            Employee(
                id=EmployeeId(i),
                name=f"Emp{i}",
                job=Job.LEAD,
                level=5,
                salary=Money(500_00),
                satisfaction=80,
                dept=Department.DEV,
            )
        )
    state = state.add_project(
        GameProject(
            id=ProjectId(1),
            title=GameTitle("X"),
            genre=Genre.RPG,
            platform=Platform.PC,
            console=None,
            progress=Progress(50),
            quality=QualityAxes(80, 80, 80, 80),
            days_in_dev=50,
            lead_id=EmployeeId(1),
            team_ids=(),
        )
    )
    strat = AggressiveStrategy()
    decisions = strat.decide(state, GameRng(0))
    hire_decisions = [d for d in decisions if d.action == "hire"]
    start_decisions = [d for d in decisions if d.action == "start_project"]
    assert len(hire_decisions) == 0
    assert len(start_decisions) == 0


def test_conservative_saves_cash_when_stable() -> None:
    state = CompanyState(cash=Money(50_000_00))
    strat = ConservativeStrategy()
    decisions = strat.decide(state, GameRng(0))
    assert any(d.action == "save_cash" for d in decisions)


def test_conservative_fires_zombie_when_low_cash() -> None:
    state = CompanyState(cash=Money(10_000_00))
    state = state.add_employee(
        Employee(
            id=EmployeeId(1),
            name="Zombie",
            job=Job.QA,
            level=1,
            salary=Money(200_00),
            satisfaction=10,  # zombie (is_zombie=True)
            dept=Department.QA,
        )
    )
    strat = ConservativeStrategy()
    decisions = strat.decide(state, GameRng(0))
    assert any(d.action == "fire" and d.target == "zombie" for d in decisions)


def test_balanced_hires_when_understaffed() -> None:
    state = CompanyState(cash=Money(100_000_00))
    strat = BalancedStrategy()
    decisions = strat.decide(state, GameRng(0))
    assert any(d.action == "hire" for d in decisions)


def test_balanced_starts_project_with_seeded_genre() -> None:
    state = CompanyState(cash=Money(100_000_00))
    strat = BalancedStrategy()
    decisions = strat.decide(state, GameRng(42))
    start = [d for d in decisions if d.action == "start_project"]
    assert len(start) == 1
    assert start[0].target in BalancedStrategy.GENRE_CHOICES


def test_genre_focus_default_rpg() -> None:
    state = CompanyState(cash=Money(50_000_00))
    strat = GenreFocusStrategy()
    decisions = strat.decide(state, GameRng(0))
    assert any(d.action == "start_project" and d.target == "RPG" for d in decisions)


def test_genre_focus_boosts_under_50pct() -> None:
    from htop_tycoon.domain import (
        GameProject,
        GameTitle,
        Platform,
        Progress,
        ProjectId,
        QualityAxes,
    )

    state = CompanyState(cash=Money(100_000_00)).add_project(
        GameProject(
            id=ProjectId(1),
            title=GameTitle("X"),
            genre=Genre.RPG,
            platform=Platform.PC,
            console=None,
            progress=Progress(30),
            quality=QualityAxes(50, 50, 50, 50),
            days_in_dev=30,
            lead_id=None,
            team_ids=(),
        )
    )
    strat = GenreFocusStrategy(focus_genre=Genre.RPG)
    decisions = strat.decide(state, GameRng(0))
    assert any(d.action == "boost_funding" for d in decisions)


def test_registry_has_all_four_kinds() -> None:
    for kind in StrategyKind:
        assert kind.value in STRATEGY_REGISTRY, f"Missing strategy for {kind.value}"


def test_current_strategy_returns_correct_instance() -> None:
    state = CompanyState(strategy=StrategyKind.AGGRESSIVE)
    strat = current_strategy(state)
    assert isinstance(strat, AggressiveStrategy)
    state2 = CompanyState(strategy=StrategyKind.BALANCED)
    assert isinstance(current_strategy(state2), BalancedStrategy)
    state3 = CompanyState(strategy=StrategyKind.GENRE_FOCUS)
    assert isinstance(current_strategy(state3), GenreFocusStrategy)


def test_strategy_decision_is_frozen() -> None:
    import pytest

    d = StrategyDecision("hire", "any", 2, "growth")
    with pytest.raises(Exception):
        d.action = "fire"  # type: ignore[misc]
