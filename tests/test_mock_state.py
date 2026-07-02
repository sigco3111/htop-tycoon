"""T1.2 RED: mock_state() factory shape."""

from __future__ import annotations

from htop_tycoon.domain import (
    Department,
    GameTitle,
    Money,
    StrategyKind,
)
from htop_tycoon.ui.mock_state import mock_state


def test_mock_state_shape() -> None:
    state = mock_state()
    assert len(state.employees) == 6
    assert len(state.projects) == 1

    depts: dict[Department, int] = {}
    for emp in state.employees.values():
        depts[emp.dept] = depts.get(emp.dept, 0) + 1
    assert depts == {
        Department.DEV: 2,
        Department.ART: 1,
        Department.SOUND: 1,
        Department.QA: 2,
    }

    zombies = [e for e in state.employees.values() if e.is_zombie]
    assert len(zombies) == 1, f"Expected exactly 1 zombie, got {len(zombies)}"

    assert state.cash == Money(100_000_00)
    assert state.fans == 0
    assert state.year == 1
    assert state.strategy == StrategyKind.BALANCED

    project = next(iter(state.projects.values()))
    assert project.progress.value == 42
    assert project.quality.fun == 60
    assert project.quality.graphics == 40
    assert project.quality.sound == 30
    assert project.quality.originality == 50
    assert project.title == GameTitle("Eldritch Quest")


def test_mock_state_employee_names() -> None:
    state = mock_state()
    names = {e.name for e in state.employees.values()}
    assert names == {"Ada", "Bob", "Carol", "Dave", "Eve", "Frank"}


def test_mock_state_deterministic() -> None:
    """Two calls return equivalent state structures."""
    s1 = mock_state()
    s2 = mock_state()
    assert len(s1.employees) == len(s2.employees)
    assert len(s1.projects) == len(s2.projects)
    assert {e.name for e in s1.employees.values()} == {e.name for e in s2.employees.values()}
