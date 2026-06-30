"""Tests for T22: GameHeader + HtopFooter widgets.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 515-524:

- ``GameHeader`` subclasses ``textual.widgets.Static`` and shows the top-line
  meta strip ``tick: 42  |  2026년 1분기 12주차  |  Engineering·5명  |  SaaS``.
- The header subscribes to ``EventBus`` and re-renders on every
  ``StateUpdated`` event (carrying the full post-transition ``GameState``).
- ``HtopFooter`` subclasses ``textual.widgets.Footer`` and shows F-key hints
  matching T24 BINDINGS EXACTLY. The locked F-row string is::

      F1도움말 F2설정 F3검색 F4필터 F5트리 F6정렬 F7승진 F8감봉 F9해고 F10매각

  and the single-key row is::

      t:트리 u:부서필터 m:만족도 s:급여 i:전략 ↑↓:이동 Space:태그

- The footer MUST NOT use htop's original English F-key labels (F7Nice-,
  F8Nice+, F9Kill, F10Quit) — those describe real htop behavior, not this
  game's actions.
- T22 + T26 + T24 BINDINGS are three sources of truth that must agree on the
  F-row labels; this test pins the T22 side so future drift is caught.

Textual widgets require an active App context (the ``Static`` widget touches
``self.app.console`` during init), so every test mounts the widget inside a
tiny ``App`` via Pilot. This matches the spec's "Pilot test" acceptance
criterion and is the only way to drive Textual widgets headlessly in CI.
"""

from __future__ import annotations

import dataclasses

from textual.app import App

from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.product import LifecycleStage, Product, ProductType
from htop_tycoon.domain.state import (
    DepartmentId,
    GameState,
    GameTime,
    ProductId,
    new_game,
)
from htop_tycoon.engine.events import EventBus, StateUpdated

# -- Locked strings (single source of truth) --------------------------------

# Plan line 516: locked F-row labels. T22 + T26 + T24 BINDINGS must agree.
LOCKED_F_ROW: str = (
    "F1도움말 F2설정 F3검색 F4필터 F5트리 "
    "F6정렬 F7승진 F8감봉 F9해고 F10매각"
)

# Plan line 516 + Wave 7: locked single-key row labels. All keys
# are lowercase. The trailing ``p:일시정지`` is the Wave-7 pause/resume
# shortcut (lowercase ``p`` → toggle_pause) registered via
# ``register_extra_bindings()``. The salary sort shortcut moved from
# ``P:급여`` to ``s:급여`` (mnemonic for "salary") and the tenure sort
# shortcut moved from ``T:입사`` to ``i:입사`` (mnemonic for "i/psa" =
# hired; ``t`` was already taken by ``toggle_tree``).
LOCKED_SINGLE_KEY_ROW: str = (
    "t:트리 u:부서필터 m:만족도 s:급여 i:전략 ↑↓:이동 Space:태그 p:일시정지 d:위임"
)

# Forbidden: htop's original English labels do NOT describe our game actions.
FORBIDDEN_ENGLISH_LABELS: tuple[str, ...] = (
    "F7Nice-",
    "F7Nice+",
    "F8Nice-",
    "F8Nice+",
    "F9Kill",
    "F10Quit",
)


# -- Fixtures ---------------------------------------------------------------


def _make_dept_with_employees(
    dept_id: str,
    *,
    dept_type: DepartmentType = DepartmentType.Engineering,
    employee_count: int = 5,
) -> Department:
    """Build a Department with ``employee_count`` placeholder employees.

    The employees themselves don't exist on the state — only the IDs are
    attached to the dept — because the header reads ``len(dept.employee_ids)``.
    """
    return Department(
        id=DepartmentId(dept_id),
        type=dept_type,
        head_employee_id=None,
        employee_ids=[
            EmployeeIdPlaceholder(f"emp-{i}")  # type: ignore[list-item]
            for i in range(employee_count)
        ],
        founded_tick=0,
        unlocked=False,
    )


class EmployeeIdPlaceholder(str):
    """A string subclass that ``Department.employee_ids`` will accept.

    The Department validator only requires ``str`` instances, so we use a
    plain string subclass to avoid pulling in the real ``EmployeeId`` NewType
    (which would require constructing Employee rows to satisfy domain
    invariants). The header reads only ``len(dept.employee_ids)``, so the
    contents don't matter for this test.
    """


def _make_product(prod_id: str = "prod-saas-1") -> Product:
    """Build a SaaS Product for the fixture."""
    return Product(
        id=ProductId(prod_id),
        type=ProductType.SaaS,
        lifecycle=LifecycleStage.intro,
        weeks_in_stage=0,
        market_share=0.5,
        revenue_per_week=1000,
    )


def _make_state(
    *,
    tick: int = 42,
    year: int = 2026,
    quarter: int = 1,
    week: int = 12,
    with_dept: bool = True,
    with_product: bool = True,
) -> GameState:
    """Build a ``GameState`` with the locked tick/time/dept/product shape.

    Defaults match the spec example: ``tick=42``, ``2026년 1분기 12주차``,
    one Engineering dept with 5 employees, one SaaS product.
    """
    base = new_game(rng_seed=42)
    departments = {}
    if with_dept:
        departments[DepartmentId("dept-eng")] = _make_dept_with_employees(
            "dept-eng",
            dept_type=DepartmentType.Engineering,
            employee_count=5,
        )
    products = {}
    if with_product:
        products[ProductId("prod-saas-1")] = _make_product("prod-saas-1")
    return dataclasses.replace(
        base,
        tick=tick,
        game_time=GameTime(year=year, quarter=quarter, week=week),
        departments=departments,
        products=products,
    )


# -- Minimal App scaffolds --------------------------------------------------


class _HeaderApp(App[None]):
    """Minimal App that mounts a GameHeader with the given bus."""

    def __init__(self, bus: EventBus) -> None:
        super().__init__()
        self._bus = bus

    def compose(self) -> object:
        # Import here to surface ImportError if the module is missing (RED).
        from htop_tycoon.ui.widgets.header import GameHeader

        yield GameHeader(self._bus)


class _FooterApp(App[None]):
    """Minimal App that mounts an HtopFooter."""

    def compose(self) -> object:
        # Import here to surface ImportError if the module is missing (RED).
        from htop_tycoon.ui.widgets.footer import HtopFooter

        yield HtopFooter()


# -- GameHeader: initial state ----------------------------------------------


class TestGameHeaderInitialState:
    """GameHeader before any StateUpdated event: empty renderable."""

    async def test_header_renders_empty_before_state_update(self) -> None:
        """Given: a fresh GameHeader (no StateUpdated yet)
        When:  mounted via Pilot
        Then:  renderable is empty string.
        """
        from htop_tycoon.ui.widgets.header import GameHeader

        bus = EventBus()
        app = _HeaderApp(bus)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one(GameHeader)
            assert str(header.renderable) == ""


# -- GameHeader: StateUpdated subscription ---------------------------------


class TestGameHeaderStateUpdated:
    """GameHeader re-renders when EventBus publishes a StateUpdated event."""

    async def test_header_updates_on_state_updated(self) -> None:
        """Given: GameHeader(bus) + state(tick=42, year=2026, Q=1, week=12)
                  + Engineering dept with 5 employees + SaaS product
        When:  bus.publish(StateUpdated(state)) is called
        Then:  header.renderable contains the exact top-line meta strip.

        The locked format is::
            tick: 42  |  2026년 1분기 12주차  |  Engineering·5명  |  SaaS
        """
        from htop_tycoon.ui.widgets.header import GameHeader

        bus = EventBus()
        app = _HeaderApp(bus)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one(GameHeader)
            state = _make_state(tick=42, year=2026, quarter=1, week=12)
            bus.publish(StateUpdated(state=state))
            await pilot.pause()
            text = str(header.renderable)
            assert "tick: 42" in text
            assert "2026년 1분기 12주차" in text
            assert "Engineering·5명" in text
            assert "SaaS" in text

    async def test_header_renders_exact_locked_top_line(self) -> None:
        """The full top-line string must match the plan's locked example exactly.

        Plan line 516 + Wave 7 (T39) regime slot:
            ``tick: 42  |  2026년 1분기 12주차  |  경기:<label><trend>  |  Engineering·5명  |  SaaS``
        """
        from htop_tycoon.ui.widgets.header import GameHeader

        bus = EventBus()
        app = _HeaderApp(bus)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one(GameHeader)
            state = _make_state(tick=42, year=2026, quarter=1, week=12)
            bus.publish(StateUpdated(state=state))
            await pilot.pause()
            expected = (
                "tick: 42  |  2026년 1분기 12주차  |  경기:보통→  |  Engineering·5명  |  SaaS"
            )
            rendered = str(header.renderable)
            # Wave 7 (T39) added the regime slot between time and dept.
            assert rendered == expected, (
                f"locked top-line drift; expected {expected!r} got {rendered!r}"
            )

    async def test_header_re_renders_on_subsequent_state_updates(self) -> None:
        """Given: header has rendered once with tick=42
        When:  a second StateUpdated with tick=99 arrives
        Then:  header shows tick=99 (not 42).
        """
        from htop_tycoon.ui.widgets.header import GameHeader

        bus = EventBus()
        app = _HeaderApp(bus)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one(GameHeader)
            bus.publish(StateUpdated(state=_make_state(tick=42)))
            await pilot.pause()
            assert "tick: 42" in str(header.renderable)
            bus.publish(StateUpdated(state=_make_state(tick=99)))
            await pilot.pause()
            assert "tick: 99" in str(header.renderable)
            assert "tick: 42" not in str(header.renderable)

    async def test_header_unchanged_when_state_unchanged(self) -> None:
        """QA failure path from the plan: tick change == 0 -> header unchanged.

        Given: header rendered with tick=42
        When:  a second StateUpdated with the SAME tick=42 fires
        Then:  the renderable stays identical (no jitter on no-op ticks).
        """
        from htop_tycoon.ui.widgets.header import GameHeader

        bus = EventBus()
        app = _HeaderApp(bus)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one(GameHeader)
            state = _make_state(tick=42)
            bus.publish(StateUpdated(state=state))
            await pilot.pause()
            first = str(header.renderable)
            bus.publish(StateUpdated(state=state))
            await pilot.pause()
            second = str(header.renderable)
            assert first == second

    async def test_header_handles_empty_departments(self) -> None:
        """No departments -> header must NOT crash; shows a placeholder."""
        from htop_tycoon.ui.widgets.header import GameHeader

        bus = EventBus()
        app = _HeaderApp(bus)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one(GameHeader)
            state = _make_state(tick=42, with_dept=False)
            bus.publish(StateUpdated(state=state))
            await pilot.pause()
            text = str(header.renderable)
            assert "tick: 42" in text
            # Must not contain the dept string when there's no dept.
            assert "Engineering" not in text

    async def test_header_handles_empty_products(self) -> None:
        """No products -> header must NOT crash; shows a placeholder."""
        from htop_tycoon.ui.widgets.header import GameHeader

        bus = EventBus()
        app = _HeaderApp(bus)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one(GameHeader)
            state = _make_state(tick=42, with_product=False)
            bus.publish(StateUpdated(state=state))
            await pilot.pause()
            text = str(header.renderable)
            assert "tick: 42" in text
            assert "SaaS" not in text


# -- HtopFooter: locked F-row labels ---------------------------------------


class TestHtopFooterFRow:
    """HtopFooter shows all 10 F-key labels matching T24 BINDINGS exactly."""

    async def test_footer_shows_locked_f_row_exactly(self) -> None:
        """The F-row string is the locked source of truth.

        Plan line 516: ``F1도움말 F2설정 ... F10매각``
        """
        from htop_tycoon.ui.widgets.footer import F_ROW, HtopFooter

        app = _FooterApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            _ = app.query_one(HtopFooter)
            # The module-level constant is the single source of truth.
            assert F_ROW == LOCKED_F_ROW

    async def test_footer_renders_f1_help(self) -> None:
        """F1도움말 appears in the rendered footer."""
        from htop_tycoon.ui.widgets.footer import HtopFooter

        app = _FooterApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.query_one(HtopFooter)
            text = _collect_text(footer)
            assert "F1도움말" in text

    async def test_footer_renders_f10_sell(self) -> None:
        """F10매각 appears in the rendered footer (matches the plan exactly)."""
        from htop_tycoon.ui.widgets.footer import HtopFooter

        app = _FooterApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.query_one(HtopFooter)
            text = _collect_text(footer)
            assert "F10매각" in text

    async def test_footer_renders_all_f_labels(self) -> None:
        """All 10 F-row labels (F1..F10) appear in the rendered footer.

        Iterates over the locked F-row tokens to catch any missing label.
        """
        from htop_tycoon.ui.widgets.footer import HtopFooter

        expected_labels = [
            "F1도움말",
            "F2설정",
            "F3검색",
            "F4필터",
            "F5트리",
            "F6정렬",
            "F7승진",
            "F8감봉",
            "F9해고",
            "F10매각",
        ]
        app = _FooterApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.query_one(HtopFooter)
            text = _collect_text(footer)
            missing = [label for label in expected_labels if label not in text]
            assert missing == [], f"missing F-row labels: {missing}"

    async def test_footer_does_not_use_htop_english_labels(self) -> None:
        """HtopFooter MUST NOT contain htop's original English F-key labels.

        Plan MUST-NOT-DO: ``F7Nice- F8Nice+ F9Kill F10Quit`` describe real
        htop behavior (process nice values, signal kill, quit), not this
        game's actions.
        """
        from htop_tycoon.ui.widgets.footer import HtopFooter

        app = _FooterApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.query_one(HtopFooter)
            text = _collect_text(footer)
            for forbidden in FORBIDDEN_ENGLISH_LABELS:
                assert forbidden not in text, (
                    f"HtopFooter leaked the forbidden htop English label {forbidden!r}"
                )


# -- HtopFooter: locked single-key row -------------------------------------


class TestHtopFooterSingleKeyRow:
    """HtopFooter shows the single-key hints matching the locked spec."""

    async def test_footer_shows_locked_single_key_row_exactly(self) -> None:
        """The single-key row string is the locked source of truth.

        Plan line 516 + Wave 7 (all keys lowercase):
        ``t:트리 u:부서필터 m:만족도 s:급여 i:입사 ↑↓:이동 Space:태그 p:일시정지``
        """
        from htop_tycoon.ui.widgets.footer import SINGLE_KEY_ROW, HtopFooter

        app = _FooterApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            _ = app.query_one(HtopFooter)
            assert SINGLE_KEY_ROW == LOCKED_SINGLE_KEY_ROW

    async def test_footer_renders_all_single_key_labels(self) -> None:
        """All 8 single-key hint tokens appear in the rendered footer.

        Wave 7 amendment: the salary token moved from ``P:급여`` to
        ``s:급여`` (so ``P`` could take the pause slot), the tenure
        token moved from ``T:입사`` to ``i:입사``, and the pause
        shortcut became lowercase ``p:일시정지``. All visual labels
        are now lowercase for consistency with the lowercase-only
        binding convention.
        """
        from htop_tycoon.ui.widgets.footer import HtopFooter

        expected = [
            "t:트리",
            "u:부서필터",
            "m:만족도",
            "s:급여",
            "i:전략",
            "↑↓:이동",
            "Space:태그",
            "p:일시정지",
        ]
        app = _FooterApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.query_one(HtopFooter)
            text = _collect_text(footer)
            missing = [label for label in expected if label not in text]
            assert missing == [], f"missing single-key labels: {missing}"


# -- Helpers ---------------------------------------------------------------


def _collect_text(widget: object) -> str:
    """Concatenate the renderable of ``widget`` and all descendant widgets.

    The footer is a ScrollableContainer; its children hold the actual text.
    For our subclass, we expect two Static children (F-row + single-key row),
    so we walk the tree to gather their renderables into a single searchable
    string. This makes the assertions robust to layout (one row vs two rows).
    """
    from textual.widget import Widget

    pieces: list[str] = [str(getattr(widget, "renderable", ""))]
    # Walk the children via the textual CSS DOM API.
    for child in getattr(widget, "children", ()):
        if isinstance(child, Widget):
            pieces.append(str(child.renderable))
            # Recurse one level so grandchildren are included.
            for grand in getattr(child, "children", ()):
                pieces.append(str(grand.renderable))
    return "\n".join(pieces)
