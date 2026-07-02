"""Phase 2I pilot: Hire + Fire screens."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Department,
    Employee,
    EmployeeId,
    Job,
    Money,
)
from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine import generate_candidates
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.fire import FireScreen, render_fire_text
from htop_tycoon.ui.screens.hire import HireScreen, render_hire_text


def _zombie() -> Employee:
    return Employee(
        id=EmployeeId(99),
        name="ZombieEve",
        job=Job.QA,
        level=2,
        salary=Money(200_00),
        satisfaction=10,
        dept=Department.QA,
    )


def test_hire_screen_renders_all_candidates() -> None:
    candidates = generate_candidates(GameRng(42), count=5)
    text = render_hire_text(candidates)
    for c in candidates:
        assert c.name in text
    assert "1." in text
    assert "5." in text


def test_hire_screen_select_returns_candidate() -> None:
    candidates = generate_candidates(GameRng(42), count=5)
    screen = HireScreen(candidates)
    picked = screen.select(1)
    assert picked == candidates[0]
    assert screen.select(99) is None
    assert screen.select(0) is None


def test_fire_screen_sorts_by_satisfaction_ascending() -> None:
    state = CompanyState().add_employee(
        Employee(
            id=EmployeeId(1),
            name="HappyAlice",
            job=Job.LEAD,
            level=5,
            salary=Money(800_00),
            satisfaction=95,
            dept=Department.DEV,
        )
    ).add_employee(_zombie())
    screen = FireScreen(state)
    assert screen.ordered[0].name == "ZombieEve"
    assert screen.ordered[1].name == "HappyAlice"


def test_fire_screen_render_marks_zombie() -> None:
    state = CompanyState().add_employee(_zombie())
    screen = FireScreen(state)
    text = render_fire_text(screen.ordered)
    assert "좀비" in text
    assert "만족도:10%" in text


def test_fire_screen_select_returns_id() -> None:
    state = CompanyState().add_employee(_zombie())
    screen = FireScreen(state)
    picked_id = screen.select(1)
    assert picked_id == EmployeeId(99)
    assert screen.select(99) is None


def test_app_hire_adds_employee() -> None:
    """action_open_hire_screen + action_select_candidate adds an employee."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _hire() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            initial_count = len(app._state.employees)
            app.action_open_hire_screen()
            await pilot.pause()
            assert app._pending_hire_screen is not None
            app.action_select_candidate("1")
            await pilot.pause()
            assert len(app._state.employees) == initial_count + 1
            assert app._pending_hire_screen is None

    asyncio.run(_hire())


def test_app_fire_removes_employee() -> None:
    """action_open_fire_screen + action_select_fire_target removes an employee."""
    app = HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(0))

    import asyncio

    async def _fire() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            initial_count = len(app._state.employees)
            app.action_open_fire_screen()
            await pilot.pause()
            assert app._pending_fire_screen is not None
            app.action_select_fire_target("1")
            await pilot.pause()
            assert len(app._state.employees) == initial_count - 1
            assert app._pending_fire_screen is None

    asyncio.run(_fire())


def test_app_fire_empty_state_no_op() -> None:
    """Firing on empty company shows notification and doesn't crash."""

    empty_state = CompanyState(strategy=StrategyKind.BALANCED, speed=0)
    app = HtopTycoonApp(state=empty_state, rng=GameRng(0))

    import asyncio

    async def _noop() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_open_fire_screen()
            await pilot.pause()
            assert app._pending_fire_screen is None

    asyncio.run(_noop())
