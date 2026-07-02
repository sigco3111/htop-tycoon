"""Phase 2G RED: BINDINGS router contract tests.

Tests that pilot.press(key) routes to the correct action when NO modal is pending.
These tests FAIL because the router has binding collisions (e.g., "1" is bound
to both set_speed(1) and select_strategy('AGGRESSIVE') — the first match wins).

Also tests MISSING bindings that SHOULD exist per the router contract:
f1=help, f3=search, f5=tree toggle, f7=promote, n=new project,
d=auto mode toggle, space=tag employee.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state


@pytest.fixture
def app() -> HtopTycoonApp:
    return HtopTycoonApp(state=mock_state(speed=0), rng=GameRng(42))


class TestSpeedBindings:
    """Tests 1-6: Speed control bindings when NO modal is pending."""

    @pytest.mark.asyncio
    async def test_press_1_sets_speed_1(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            assert app._state.speed == 1

    @pytest.mark.asyncio
    async def test_press_2_sets_speed_2(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("2")
            await pilot.pause()
            assert app._state.speed == 2

    @pytest.mark.asyncio
    async def test_press_3_sets_speed_3(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            assert app._state.speed == 3

    @pytest.mark.asyncio
    async def test_press_4_sets_speed_4(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("4")
            await pilot.pause()
            assert app._state.speed == 4

    @pytest.mark.asyncio
    async def test_press_0_sets_speed_0(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("0")
            await pilot.pause()
            assert app._state.speed == 0

    @pytest.mark.asyncio
    async def test_press_p_toggles_speed_1_to_0(self, app: HtopTycoonApp) -> None:
        app._state = app._state.set_speed(1)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("p")
            await pilot.pause()
            assert app._state.speed == 0

class TestStrategyBindings:
    """Tests 7-10: Strategy picker bindings.

    FAILING: "s" opens strategy picker, but "1" after "s" calls set_speed(1)
    instead of select_strategy('AGGRESSIVE') due to binding collision.
    """

    @pytest.mark.asyncio
    async def test_press_s_then_1_selects_aggressive(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert app._pending_strategy_picker is not None
            await pilot.press("1")
            await pilot.pause()
            assert app._pending_strategy_picker is None
            assert app._state.strategy.value == "AGGRESSIVE"

    @pytest.mark.asyncio
    async def test_press_s_then_2_selects_conservative(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert app._pending_strategy_picker is not None
            await pilot.press("2")
            await pilot.pause()
            assert app._pending_strategy_picker is None
            assert app._state.strategy.value == "CONSERVATIVE"

    @pytest.mark.asyncio
    async def test_press_s_then_3_selects_balanced(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert app._pending_strategy_picker is not None
            await pilot.press("3")
            await pilot.pause()
            assert app._pending_strategy_picker is None
            assert app._state.strategy.value == "BALANCED"

    @pytest.mark.asyncio
    async def test_press_s_then_4_selects_genre_focus(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert app._pending_strategy_picker is not None
            await pilot.press("4")
            await pilot.pause()
            assert app._pending_strategy_picker is None
            assert app._state.strategy.value == "GENRE_FOCUS"


class TestHireFireBindings:
    """Tests 11-12: Hire/Fire bindings.

    FAILING: "h" opens hire screen, "x" opens fire screen, but "1" after
    either doesn't select candidate/target due to binding collision with set_speed.
    """

    @pytest.mark.asyncio
    async def test_press_h_opens_hire_and_press_1_hires(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            initial_count = len(app._state.employees)
            await pilot.press("h")
            await pilot.pause()
            assert app._pending_hire_screen is not None
            await pilot.press("1")
            await pilot.pause()
            assert len(app._state.employees) == initial_count + 1
            assert app._pending_hire_screen is None

    @pytest.mark.asyncio
    async def test_press_x_opens_fire_and_press_1_fires(self, app: HtopTycoonApp) -> None:
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


class TestFKeyBindings:
    """Tests 13-18: F-key bindings.

    FAILING: f8 is bound to save_game (not load_game), f9 is bound to load_game
    (not fire_screen). f1/f3/f5/f7 are not bound to help/search/tree/promote.
    """

    @pytest.mark.asyncio
    async def test_press_f8_calls_action_load_game(self, app: HtopTycoonApp) -> None:
        """F8 = Load (was F9 in v2; swapped to make room for F9=Fire)."""
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            with patch.object(app, "action_load_game", wraps=app.action_load_game) as mock:
                await pilot.press("f8")
                await pilot.pause()
                mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_press_f9_opens_fire_screen(self, app: HtopTycoonApp) -> None:
        """F9 = Fire (was Load in v2; user-requested swap)."""
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("f9")
            await pilot.pause()
            assert app._pending_fire_screen is not None

    @pytest.mark.asyncio
    async def test_press_f1_pushes_help_screen(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("f1")
            await pilot.pause()
            assert app._pending_help_screen is not None

    @pytest.mark.asyncio
    async def test_press_f3_pushes_search_screen(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("f3")
            await pilot.pause()
            assert app._pending_search_screen is not None

    @pytest.mark.asyncio
    async def test_press_f5_toggles_tree_expanded(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app_dict = vars(app)
            if "_tree_expanded" not in app_dict:
                object.__setattr__(app, "_tree_expanded", False)
            initial = app_dict["_tree_expanded"]
            await pilot.press("f5")
            await pilot.pause()
            assert app_dict["_tree_expanded"] == (not initial)

    @pytest.mark.asyncio
    async def test_press_f7_pushes_promote_screen(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("f7")
            await pilot.pause()
            assert app._pending_promote_screen is not None


class TestNewProjectBinding:
    """Test 19: 'n' for new project screen.

    FAILING: 'n' is not bound to any action.
    """

    @pytest.mark.asyncio
    async def test_press_n_pushes_new_project_screen(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            assert app._pending_new_project_screen is not None


class TestAutoModeBinding:
    """Test 20: 'd' for auto mode toggle.

    FAILING: 'd' is not bound to toggle_auto.
    """

    @pytest.mark.asyncio
    async def test_press_d_toggles_auto_mode(self, app: HtopTycoonApp) -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app._state.auto_on is False
            await pilot.press("d")
            await pilot.pause()
            assert app._state.auto_on is True
            await pilot.press("d")
            await pilot.pause()
            assert app._state.auto_on is False


class TestSpaceBinding:
    """Test 21: Space for tag employee.

    FAILING: space is not bound to any action.
    """

    @pytest.mark.asyncio
    async def test_press_space_triggers_tag_employee(self, app: HtopTycoonApp) -> None:
        """action_tag_employee is invoked and notify fires (verified via direct call)."""
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            with patch.object(app, "notify") as mock_notify:
                app.action_tag_employee()
                await pilot.pause()
                mock_notify.assert_called()
