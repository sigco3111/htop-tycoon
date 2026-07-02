"""T3 RED: serialize roundtrip — Money, IDs, enums, tuple, None, etc."""

from __future__ import annotations

import pytest

from htop_tycoon.domain import (
    CompanyState,
    Console,
    Department,
    Employee,
    EmployeeId,
    GameProject,
    GameTitle,
    Genre,
    Job,
    Money,
    Platform,
    Progress,
    ProjectId,
    QualityAxes,
    StrategyKind,
)
from htop_tycoon.ui.mock_state import mock_state


def test_roundtrip_empty_state() -> None:
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = CompanyState()
    text = to_yaml(state)
    restored = from_yaml(text)
    assert restored == state


def test_roundtrip_mock_state() -> None:
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = mock_state(speed=1)
    text = to_yaml(state)
    restored = from_yaml(text)
    assert restored.year == state.year
    assert restored.cash.cents == state.cash.cents
    assert restored.fans == state.fans
    assert restored.strategy == state.strategy
    assert restored.speed == state.speed
    assert restored.rng_seed == state.rng_seed
    assert len(restored.employees) == len(state.employees)
    assert len(restored.projects) == len(state.projects)
    for eid, emp in state.employees.items():
        r_emp = restored.employees[eid]
        assert r_emp == emp
        assert type(r_emp.id) is EmployeeId
    for pid, proj in state.projects.items():
        r_proj = restored.projects[pid]
        assert r_proj == proj
        assert type(r_proj.id) is ProjectId
        assert type(r_proj.lead_id) is type(proj.lead_id)


def test_money_cents_round_trips_as_int() -> None:
    """Money.cents must serialize as a bare int (not float, not nested dict)."""
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = CompanyState(cash=Money(1_234_56))
    text = to_yaml(state)
    assert "123456" in text, f"cash cents not serialized as int: {text}"
    restored = from_yaml(text)
    assert restored.cash == Money(1_234_56)


def test_team_ids_round_trip_as_tuple() -> None:
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = CompanyState().add_employee(
        Employee(
            id=EmployeeId(1),
            name="Ada",
            job=Job.LEAD,
            level=5,
            salary=Money(880_00),
            satisfaction=85,
            dept=Department.DEV,
        )
    ).add_project(
        GameProject(
            id=ProjectId(1),
            title=GameTitle("Test"),
            genre=Genre.RPG,
            platform=Platform.PC,
            console=None,
            progress=Progress(50),
            quality=QualityAxes(60, 40, 30, 50),
            days_in_dev=50,
            lead_id=EmployeeId(1),
            team_ids=(EmployeeId(1), EmployeeId(2)),
        )
    )
    restored = from_yaml(to_yaml(state))
    assert isinstance(restored.projects[ProjectId(1)].team_ids, tuple)
    assert restored.projects[ProjectId(1)].team_ids == (
        EmployeeId(1),
        EmployeeId(2),
    )


def test_console_none_round_trips() -> None:
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = CompanyState().add_project(
        GameProject(
            id=ProjectId(1),
            title=GameTitle("PC Game"),
            genre=Genre.RPG,
            platform=Platform.PC,
            console=None,
            progress=Progress(0),
            quality=QualityAxes(),
            days_in_dev=0,
            lead_id=None,
            team_ids=(),
        )
    )
    restored = from_yaml(to_yaml(state))
    assert restored.projects[ProjectId(1)].console is None


def test_console_value_round_trips() -> None:
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = CompanyState().add_project(
        GameProject(
            id=ProjectId(1),
            title=GameTitle("Console Game"),
            genre=Genre.ACTION,
            platform=Platform.CONSOLE,
            console=Console.NOVA,
            progress=Progress(10),
            quality=QualityAxes(),
            days_in_dev=10,
            lead_id=None,
            team_ids=(),
        )
    )
    restored = from_yaml(to_yaml(state))
    assert restored.projects[ProjectId(1)].console == Console.NOVA


def test_strategy_kind_round_trips() -> None:
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = CompanyState(strategy=StrategyKind.AGGRESSIVE)
    restored = from_yaml(to_yaml(state))
    assert restored.strategy == StrategyKind.AGGRESSIVE


def test_quality_axes_round_trip() -> None:
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = CompanyState().add_project(
        GameProject(
            id=ProjectId(1),
            title=GameTitle("Q"),
            genre=Genre.RPG,
            platform=Platform.PC,
            console=None,
            progress=Progress(0),
            quality=QualityAxes(10, 20, 30, 40),
            days_in_dev=0,
            lead_id=None,
            team_ids=(),
        )
    )
    restored = from_yaml(to_yaml(state))
    assert restored.projects[ProjectId(1)].quality == QualityAxes(10, 20, 30, 40)


def test_game_title_strips_whitespace() -> None:
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = CompanyState().add_project(
        GameProject(
            id=ProjectId(1),
            title=GameTitle("  Spaces  "),
            genre=Genre.RPG,
            platform=Platform.PC,
            console=None,
            progress=Progress(0),
            quality=QualityAxes(),
            days_in_dev=0,
            lead_id=None,
            team_ids=(),
        )
    )
    restored = from_yaml(to_yaml(state))
    assert restored.projects[ProjectId(1)].title == GameTitle("Spaces")


def test_unknown_enum_raises() -> None:
    from htop_tycoon.persistence.serialize import PersistenceVersionError, from_yaml

    yaml_text = """
version: 1
state:
  year: 1
  day_index: 0
  cash: 10000000
  fans: 0
  strategy: NOT_AN_ENUM
  auto_on: false
  speed: 0
  rng_seed: 42
  employees: []
  projects: []
"""
    with pytest.raises((ValueError, PersistenceVersionError)):
        from_yaml(yaml_text)


def test_negative_cash_round_trips() -> None:
    from htop_tycoon.persistence.serialize import from_yaml, to_yaml

    state = CompanyState(cash=Money(-50_00))
    restored = from_yaml(to_yaml(state))
    assert restored.cash == Money(-50_00)
