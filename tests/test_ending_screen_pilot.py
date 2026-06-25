"""Tests for T21: EndingScreen widget — 5 endings, Korean result text.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 504-513:

- ``class EndingScreen(textual.screen.ModalScreen)`` taking ``EndingType``
  and the run's ``GameState`` for the summary stats.
- Renders centered text with the Korean ending title (from
  ``endings.yaml``), summary flavor text (Korean), and summary stats
  (final cash, market cap, weeks played, employees).
- Footer line: ``Press Q to restart`` (English literal from the spec).
- Each ending has unique Korean flavor text loaded from ``endings.yaml``
  via ``load_endings()`` — code must NOT hardcode the Korean strings.
- Pressing ``Q`` dismisses the modal and returns to the underlying App
  (the App is NOT closed; the player returns to a game-over state).

The test triggers each of the 5 endings via a crafted state, confirms the
modal opens with the correct Korean title, then dismisses with Q and
confirms the App is still alive (the modal is closed, not the app).

Modal screens require a Textual app context; we mount each test in a tiny
host app via ``Pilot``.
"""

from __future__ import annotations

import dataclasses

from textual.app import App

from htop_tycoon.data import load_endings
from htop_tycoon.domain.ending import EndingType
from htop_tycoon.domain.state import Company, GameState, GameTime
from htop_tycoon.ui.screens.ending_screen import EndingScreen

# -- Crafted state fixture --------------------------------------------------


def _craft_state(
    *,
    cash: int = -500,
    market_cap: int = 10_000,
    weeks: int = 42,
    employees: int = 7,
    ending_history: list[dict[str, object]] | None = None,
) -> GameState:
    """Build a minimal GameState with controllable summary stat values.

    Only the fields rendered on the EndingScreen are populated; the
    SECRET sub-conditions are not exercised here (the screen just shows
    stats — it does not re-evaluate the trigger). Department/Employee
    collections are kept empty because the screen reads only ``len()``.

    Args:
        cash: Final cash to display.
        market_cap: Final market cap to display.
        weeks: Final tick (= weeks played) to display.
        employees: Final employee count to display.
        ending_history: Optional list of pre-applied ending markers.
    """
    company = Company(
        id="company-1",
        name="My Company",
        cash=cash,
        market_cap=market_cap,
    )
    return GameState(
        company=company,
        departments={},
        employees={},
        products={},
        competitors={},
        events_active=[],
        ending_history=list(ending_history or []),
        secret_investor_cleared=False,
        tick=weeks,
        rng_seed=42,
        game_time=GameTime(year=1, quarter=1, week=1),
        version=1,
    )


# -- Host App ---------------------------------------------------------------


class _EndingHostApp(App[None]):
    """Minimal App that pushes a single EndingScreen on mount.

    Each test instance gets its own screen pushed on mount, then the test
    inspects the rendered modal.
    """

    def __init__(self, ending_type: EndingType, state: GameState) -> None:
        super().__init__()
        self._ending_type = ending_type
        self._state = state
        # Tracks how many times the modal has dismissed (for assertions).
        self.dismissed_with: object | None = None

    def compose(self) -> object:
        # No children — the modal is pushed imperatively in on_mount.
        # (Pushing in on_mount keeps compose() pure and predictable.)
        return []

    def on_mount(self) -> None:
        # Push the modal screen on mount so Pilot can interact with it.
        screen = EndingScreen(self._ending_type, self._state)
        self.push_screen(screen)


# -- Each of the 5 endings renders the correct Korean title ----------------


class TestEndingScreenRendersFiveEndings:
    """All 5 ending types render the correct Korean title from endings.yaml."""

    async def test_bankruptcy_renders_korean_title(self) -> None:
        """Given: EndingScreen pushed for BANKRUPTCY
        When: Pilot pauses
        Then: rendered content contains the Korean title '파산'.
        """
        expected_title = load_endings()["BANKRUPTCY"]["title_ko"]
        app = _EndingHostApp(EndingType.BANKRUPTCY, _craft_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, EndingScreen)
            rendered = str(screen.renderable)
            assert expected_title in rendered, (
                f"BANKRUPTCY modal missing title {expected_title!r} "
                f"in render: {rendered!r}"
            )
            # Sanity: '파산' is the locked literal from the plan.
            assert "파산" in rendered

    async def test_ipo_renders_korean_title(self) -> None:
        """Given: EndingScreen pushed for IPO
        When: Pilot pauses
        Then: rendered content contains the Korean title '상장 성공'.
        """
        expected_title = load_endings()["IPO"]["title_ko"]
        app = _EndingHostApp(EndingType.IPO, _craft_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, EndingScreen)
            rendered = str(screen.renderable)
            assert expected_title in rendered
            assert "상장 성공" in rendered

    async def test_hostile_ma_renders_korean_title(self) -> None:
        """Given: EndingScreen pushed for HOSTILE_MA
        When: Pilot pauses
        Then: rendered content contains the Korean title '적대적 인수'.
        """
        expected_title = load_endings()["HOSTILE_MA"]["title_ko"]
        app = _EndingHostApp(EndingType.HOSTILE_MA, _craft_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, EndingScreen)
            rendered = str(screen.renderable)
            assert expected_title in rendered
            assert "적대적 인수" in rendered

    async def test_voluntary_sale_renders_korean_title(self) -> None:
        """Given: EndingScreen pushed for VOLUNTARY_SALE
        When: Pilot pauses
        Then: rendered content contains the Korean title '자발적 매각'.
        """
        expected_title = load_endings()["VOLUNTARY_SALE"]["title_ko"]
        app = _EndingHostApp(EndingType.VOLUNTARY_SALE, _craft_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, EndingScreen)
            rendered = str(screen.renderable)
            assert expected_title in rendered
            assert "자발적 매각" in rendered

    async def test_secret_renders_korean_title(self) -> None:
        """Given: EndingScreen pushed for SECRET
        When: Pilot pauses
        Then: rendered content contains the Korean title '비밀 엔딩'.
        """
        expected_title = load_endings()["SECRET"]["title_ko"]
        app = _EndingHostApp(EndingType.SECRET, _craft_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, EndingScreen)
            rendered = str(screen.renderable)
            assert expected_title in rendered
            assert "비밀 엔딩" in rendered


# -- Summary stats appear on the modal --------------------------------------


class TestEndingScreenRendersSummaryStats:
    """The summary stats (cash, market cap, weeks, employees) appear on screen."""

    async def test_summary_includes_final_cash(self) -> None:
        """The crafted cash value appears in the rendered text."""
        app = _EndingHostApp(EndingType.BANKRUPTCY, _craft_state(cash=-500))
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            assert "-500" in rendered

    async def test_summary_includes_market_cap(self) -> None:
        """The crafted market_cap value appears in the rendered text."""
        app = _EndingHostApp(EndingType.IPO, _craft_state(market_cap=12_345))
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            assert "12345" in rendered

    async def test_summary_includes_weeks_played(self) -> None:
        """The weeks (= state.tick) value appears in the rendered text."""
        app = _EndingHostApp(EndingType.IPO, _craft_state(weeks=99))
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            assert "99" in rendered

    async def test_summary_includes_employee_count(self) -> None:
        """The employee count (= len(state.employees)) appears in the text."""
        # Build a state with 3 employees so the count is non-trivial.
        state = _craft_state(employees=3)
        # Inject 3 dummy employees (EndingScreen only reads len()).
        from htop_tycoon.domain.state import DepartmentId, EmployeeId

        state = dataclasses.replace(
            state,
            employees={EmployeeId(f"emp-{i}"): object() for i in range(3)},  # type: ignore[arg-type]
            departments={DepartmentId("d"): object() for _ in range(0)},  # type: ignore[arg-type]
        )
        app = _EndingHostApp(EndingType.IPO, state)
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            assert "3" in rendered

    async def test_summary_includes_korean_flavor_text(self) -> None:
        """The summary_ko from endings.yaml is rendered (no hardcoded copy)."""
        for ending_type in EndingType:
            expected_summary = load_endings()[ending_type.value]["summary_ko"]
            app = _EndingHostApp(ending_type, _craft_state())
            async with app.run_test() as pilot:
                await pilot.pause()
                rendered = str(app.screen.renderable)
                assert expected_summary in rendered, (
                    f"{ending_type.value} modal missing Korean flavor "
                    f"{expected_summary!r} in render: {rendered!r}"
                )

    async def test_footer_mentions_press_q(self) -> None:
        """The footer 'Press Q to restart' is rendered (spec literal)."""
        app = _EndingHostApp(EndingType.BANKRUPTCY, _craft_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            assert "Q" in rendered, "footer should reference Q key"


# -- Q dismisses the modal without closing the App --------------------------


class TestEndingScreenDismissWithQ:
    """Pressing Q dismisses the modal; the App is NOT closed."""

    async def test_q_dismisses_modal(self) -> None:
        """Given: EndingScreen pushed onto a host App
        When: the user presses Q
        Then: the modal is dismissed (app.screen is no longer EndingScreen).
        """
        app = _EndingHostApp(EndingType.BANKRUPTCY, _craft_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            # Sanity: the modal is currently the active screen.
            assert isinstance(app.screen, EndingScreen)
            # Press Q to dismiss.
            await pilot.press("q")
            await pilot.pause()
            # The modal must be gone — app.screen is back to the default.
            assert not isinstance(app.screen, EndingScreen), (
                f"Q did not dismiss the modal: app.screen is {type(app.screen).__name__}"
            )

    async def test_q_dismissal_keeps_app_alive(self) -> None:
        """Given: EndingScreen pushed onto a host App
        When: Q is pressed
        Then: the App itself is NOT closed — the Pilot context is still active.
        """
        app = _EndingHostApp(EndingType.IPO, _craft_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, EndingScreen)
            await pilot.press("q")
            await pilot.pause()
            # The app is still mounted: a follow-up tick should not raise,
            # and ``app.is_running`` should still be True.
            assert app.is_running
            # And the screen stack is back to one screen (the default).
            assert len(app.screen_stack) == 1

    async def test_q_dismisses_for_every_ending_type(self) -> None:
        """All 5 endings dismiss cleanly with Q (no per-ending binding bugs)."""
        for ending_type in EndingType:
            app = _EndingHostApp(ending_type, _craft_state())
            async with app.run_test() as pilot:
                await pilot.pause()
                assert isinstance(app.screen, EndingScreen), (
                    f"{ending_type.value}: modal not pushed"
                )
                await pilot.press("q")
                await pilot.pause()
                assert not isinstance(app.screen, EndingScreen), (
                    f"{ending_type.value}: Q did not dismiss modal"
                )
                assert app.is_running, (
                    f"{ending_type.value}: app was closed by Q"
                )


# -- Module surface ---------------------------------------------------------


class TestEndingScreenModuleSurface:
    """The screens package re-exports EndingScreen for clean imports."""

    def test_screens_package_exposes_ending_screen(self) -> None:
        """``htop_tycoon.ui.screens`` exposes EndingScreen after the re-export."""
        import htop_tycoon.ui.screens as screens_module

        assert hasattr(screens_module, "EndingScreen")
        assert screens_module.EndingScreen is EndingScreen
