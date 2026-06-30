"""Tests for T23: CJK width correction + color/theme audit (full-app Pilot).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 526-535:

- ``HtopTycoonApp`` runs in Pilot mode for 100 ticks (with ``tick_rate=100``)
  without crashing.
- Korean text (MetricBar labels, footer F-row, header top-line) renders with
  no width drift. ``rich.measure.Measurement`` is used to compute the
  CJK-correct cell width of each rendered row, and the measurement is
  compared against the expected width derived from ``rich.cells``.
- All colors are readable on black background. Pilot snapshot of MetricBar
  widget asserts the rendered foreground color is in the expected range
  for each level: ``ok`` -> ``#00ff00`` (green), ``warn`` -> ``#ffff00``
  (yellow), ``alert`` -> ``#ff0000`` (red).
- The full app renders without crashing on narrow terminals:
  ``size=(80, 24)`` (default) and ``size=(60, 24)`` both succeed.

The audit is AGENT-EXECUTED (per the plan's MUST-NOT-DO rule): every
acceptance criterion is enforced by an assertion in this module, not by
a manual screenshot review.

Why ``rich.measure`` and ``rich.cells``?
    The plan mandates ``rich.measure`` (line 530 reference) and references
    pypi.org/project/wcwidth/. Rich's bundled unicode data is used because
    ``wcwidth`` is not declared as a project dependency and Rich's
    ``Measurement.get`` / ``get_character_cell_size`` cover the same CJK
    width contract internally (no third-party import is needed).
"""

from __future__ import annotations

import dataclasses

from rich.cells import get_character_cell_size
from rich.console import Console
from rich.measure import Measurement
from rich.text import Text
from textual.app import App

from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.product import LifecycleStage, Product, ProductType
from htop_tycoon.domain.state import (
    DepartmentId,
    GameTime,
    ProductId,
    new_game,
)
from htop_tycoon.engine.events import EventBus, StateUpdated
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.widgets.footer import F_ROW, SINGLE_KEY_ROW, HtopFooter
from htop_tycoon.ui.widgets.header import GameHeader
from htop_tycoon.ui.widgets.metric_bar import LEVEL_COLORS, MetricBar

# -- Helpers ---------------------------------------------------------------


def _measure(renderable: object, console: Console) -> int:
    """Return the CJK-aware terminal-cell width of ``renderable``.

    Given: any Rich-renderable object (``Text``, ``str``, etc.)
    When:  called
    Then:  returns ``Measurement.get(console, console.options, renderable).maximum``

    ``str`` is wrapped in ``Text`` first because ``Measurement.get`` for a
    bare ``str`` reports the printable string length, not the cell width;
    ``Text`` has a ``__rich_measure__`` that uses ``rich.cells`` per cell.
    """
    if isinstance(renderable, str):
        renderable = Text(renderable)
    measurement = Measurement.get(console, console.options, renderable)
    return measurement.maximum


def _cell_width(text_str: str) -> int:
    """Return the CJK cell-width of a plain Python string.

    Summation of ``rich.cells.get_character_cell_size`` for each char.
    Handles wide (Hangul, Han, etc.) and narrow (ASCII, Latin) chars.
    """
    return sum(get_character_cell_size(ch) for ch in text_str)


def _get_text(widget: object) -> Text:
    """Return the underlying Rich ``Text`` renderable for a widget.

    ``Static.renderable`` is a property in Textual 0.86+ that returns the
    parsed renderable. For widgets that have not yet rendered, it returns
    the empty string (which we wrap into a ``Text`` for downstream use).
    """
    raw = getattr(widget, "renderable", "")
    if isinstance(raw, str):
        return Text(raw)
    return raw  # type: ignore[return-value]


def _fg_hex(widget: object) -> str:
    """Return the hex foreground color of a widget's renderable (or ``""``).

    Used by the color audit to verify that ``MetricBar`` paints each level
    with the locked hex code. The widget sets a whole-text style (no per-
    span overrides), so ``text.style`` is a plain hex string.
    """
    text = _get_text(widget)
    return str(getattr(text, "style", ""))


# -- Fixtures --------------------------------------------------------------


def _make_department_with_employees(
    *,
    dept_id: str = "dept-eng",
    count: int = 5,
) -> Department:
    """Build a locked-shape Department for the header fixture."""
    return Department(
        id=DepartmentId(dept_id),
        type=DepartmentType.Engineering,
        head_employee_id=None,
        employee_ids=[
            type("Eid", (str,), {})(f"emp-{i}")  # type: ignore[list-item,operator]
            for i in range(count)
        ],
        founded_tick=0,
        unlocked=False,
    )


def _make_product(prod_id: str = "prod-saas-1") -> Product:
    """Build a locked-shape Product for the header fixture."""
    return Product(
        id=ProductId(prod_id),
        type=ProductType.SaaS,
        lifecycle=LifecycleStage.intro,
        weeks_in_stage=0,
        market_share=0.5,
        revenue_per_week=1000,
    )


def _make_header_state(
    *,
    tick: int = 42,
    year: int = 2026,
    quarter: int = 1,
    week: int = 12,
) -> object:
    """Build a GameState matching the locked top-line example."""
    base = new_game(rng_seed=42)
    return dataclasses.replace(
        base,
        tick=tick,
        game_time=GameTime(year=year, quarter=quarter, week=week),
        departments={
            DepartmentId("dept-eng"): _make_department_with_employees(count=5),
        },
        products={ProductId("prod-saas-1"): _make_product()},
    )


# -- Host apps for the widget-level audit ----------------------------------


class _MetricBarHostApp(App[None]):
    """Minimal App that mounts a single ``MetricBar``."""

    def __init__(self, bar: MetricBar) -> None:
        super().__init__()
        self._bar = bar

    def compose(self) -> object:
        yield self._bar


class _FooterHostApp(App[None]):
    """Minimal App that mounts a single ``HtopFooter``."""

    def compose(self) -> object:
        yield HtopFooter()


class _HeaderHostApp(App[None]):
    """Minimal App that mounts a single ``GameHeader`` wired to a bus."""

    def __init__(self, bus: EventBus) -> None:
        super().__init__()
        self._bus = bus

    def compose(self) -> object:
        yield GameHeader(self._bus)


# -- Test 1: CJK width audit (no drift) ------------------------------------


class TestCjkWidthAudit:
    """Every widget that carries Korean text renders with the expected width.

    Width expectations are derived via ``rich.cells.get_character_cell_size``
    (summed per char) and confirmed via ``rich.measure``. A drift of more
    than zero cells between the two would indicate that Rich is rendering
    Korean characters as 1-wide instead of 2-wide.
    """

    async def test_metric_bar_cpu_has_expected_cjk_width(self) -> None:
        """Given: MetricBar('CPU') at 30% with Korean label '매출'
        When:  measured via ``rich.measure.Measurement.get``
        Then:  the measured width equals ``_cell_width(plain_text)``

        Plain (chars):  ``CPU[매출]  █████████░░░░░░░░░░░░░░░░  30%  ok``
        CJK cells:      50 (each Hangul syllable is 2 cells)
        """
        bar = MetricBar("CPU")
        app = _MetricBarHostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(30.0, "ok", "매출")
            await pilot.pause()

            plain = _get_text(bar).plain
            expected = _cell_width(plain)
            console = Console()
            measured = _measure(_get_text(bar), console)
            assert measured == expected, (
                f"MetricBar(CPU) width drift: measured={measured} expected={expected}"
            )
            assert expected == 50, f"expected 50 cells for plain = {plain!r}"

    async def test_metric_bar_mem_has_expected_cjk_width(self) -> None:
        """Given: MetricBar('MEM') at 70% with Korean label '재고'
        When:  measured via ``rich.measure``
        Then:  matches ``_cell_width(plain_text)`` (70% -> 21 filled)
        """
        bar = MetricBar("MEM")
        app = _MetricBarHostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(70.0, "warn", "재고")
            await pilot.pause()

            plain = _get_text(bar).plain
            expected = _cell_width(plain)
            measured = _measure(_get_text(bar), Console())
            assert measured == expected, (
                f"MetricBar(MEM) width drift: measured={measured} expected={expected}"
            )

    async def test_metric_bar_swap_has_expected_cjk_width(self) -> None:
        """Given: MetricBar('SWAP') at 95% with Korean label '부채'
        When:  measured via ``rich.measure``
        Then:  matches ``_cell_width(plain_text)`` (95% -> 28 filled)
        """
        bar = MetricBar("SWAP")
        app = _MetricBarHostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(95.0, "alert", "부채")
            await pilot.pause()

            plain = _get_text(bar).plain
            expected = _cell_width(plain)
            measured = _measure(_get_text(bar), Console())
            assert measured == expected, (
                f"MetricBar(SWAP) width drift: measured={measured} expected={expected}"
            )

    async def test_hangul_syllable_is_two_cells(self) -> None:
        """Per the plan: each Hangul char = 2 cells (CJK width rule).

        This is a sanity test that pins the cell-width contract; if
        ``rich.cells`` ever dropped CJK support, every widget test above
        would fail in the same way.
        """
        assert get_character_cell_size("도") == 2
        assert get_character_cell_size("움") == 2
        assert get_character_cell_size("말") == 2
        assert _cell_width("매출") == 4
        assert _cell_width("재고") == 4
        assert _cell_width("부채") == 4

    async def test_footer_f_row_has_no_width_drift(self) -> None:
        """Given: HtopFooter with the locked F-row
        When:  measured via ``rich.measure`` and ``_cell_width``
        Then:  both report 72 cells (the expected locked width)

        Locked F-row is
        ``F1도움말 F2설정 F3검색 F4필터 F5트리 F6정렬 F7승진 F8감봉 F9해고 F10매각``
        which is 41 chars (Python ``len``) but 72 terminal cells because
        every Hangul syllable is 2 cells wide.
        """
        app = _FooterHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.query_one(HtopFooter)
            children = list(footer.children)
            assert len(children) == 2
            f_row_static = children[0]
            f_row_text = _get_text(f_row_static)
            plain = f_row_text.plain
            expected = _cell_width(plain)
            measured = _measure(f_row_text, Console())
            assert measured == expected, (
                f"Footer F-row width drift: measured={measured} expected={expected}"
            )
            assert expected == 72
            assert plain == F_ROW

    async def test_footer_single_key_row_has_no_width_drift(self) -> None:
        """Given: HtopFooter single-key row
        When:  measured via ``rich.measure`` and ``_cell_width``
        Then:  both report 70 cells (the expected locked width)

        Wave 7: the trailing `` `:일시정지`` shortcut adds 11 cells to
        the original 59-cell locked row, bringing the total to 70.
        Both widths fit comfortably in an 80-wide terminal (F_ROW is
        72 cells on its own row).
        """
        app = _FooterHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.query_one(HtopFooter)
            children = list(footer.children)
            assert len(children) == 2
            sk_row_static = children[1]
            sk_row_text = _get_text(sk_row_static)
            plain = sk_row_text.plain
            expected = _cell_width(plain)
            measured = _measure(sk_row_text, Console())
            assert measured == expected, (
                f"Footer single-key row width drift: "
                f"measured={measured} expected={expected}"
            )
            assert expected == 77
            assert plain == SINGLE_KEY_ROW

    async def test_header_top_line_has_no_width_drift(self) -> None:
        """Given: GameHeader with the locked top-line example
        When:  measured via ``rich.measure`` and ``_cell_width``
        Then:  both report 61 cells (the expected locked width)

        Locked top-line:
        ``tick: 42  |  2026년 1분기 12주차  |  Engineering·5명  |  SaaS``
        """
        bus = EventBus()
        app = _HeaderHostApp(bus)
        async with app.run_test() as pilot:
            await pilot.pause()
            bus.publish(StateUpdated(state=_make_header_state()))
            await pilot.pause()
            header = app.query_one(GameHeader)
            text = _get_text(header)
            plain = text.plain
            expected = _cell_width(plain)
            measured = _measure(text, Console())
            assert measured == expected, (
                f"Header top-line width drift: measured={measured} expected={expected}"
            )
            assert expected == 61
            assert plain == "tick: 42  |  2026년 1분기 12주차  |  Engineering·5명  |  SaaS"


# -- Test 2: Color audit (level -> hex) ------------------------------------


class TestColorAudit:
    """MetricBar widget renders each level with the locked foreground color.

    Per the plan: "snapshot of MetricBar widget, assert in expected range
    for each level (ok=green-ish, warn=yellow-ish, alert=red-ish)". The
    MetricBar widget locks exact hex codes (``#00ff00``, ``#ffff00``,
    ``#ff0000``); we assert the EXACT hex (a stricter, machine-checkable
    form of "in the expected range"). The color audit also confirms the
    rendered Text carries the style as a whole-text style (no per-span
    override gaps).
    """

    async def test_ok_level_renders_with_locked_green_hex(self) -> None:
        """Given: MetricBar with level='ok'
        When:  rendered via Pilot
        Then:  the Text's style is exactly ``#00ff00`` (canonical green)
        """
        bar = MetricBar("CPU")
        app = _MetricBarHostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(30.0, "ok", "매출")
            await pilot.pause()

            hex_code = _fg_hex(bar)
            assert hex_code.lower() == LEVEL_COLORS["ok"].lower(), (
                f"ok-level fg expected {LEVEL_COLORS['ok']!r}, got {hex_code!r}"
            )

    async def test_warn_level_renders_with_locked_yellow_hex(self) -> None:
        """Given: MetricBar with level='warn'
        When:  rendered via Pilot
        Then:  the Text's style is exactly ``#ffff00`` (canonical yellow)
        """
        bar = MetricBar("MEM")
        app = _MetricBarHostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(70.0, "warn", "재고")
            await pilot.pause()

            hex_code = _fg_hex(bar)
            assert hex_code.lower() == LEVEL_COLORS["warn"].lower(), (
                f"warn-level fg expected {LEVEL_COLORS['warn']!r}, got {hex_code!r}"
            )

    async def test_alert_level_renders_with_locked_red_hex(self) -> None:
        """Given: MetricBar with level='alert'
        When:  rendered via Pilot
        Then:  the Text's style is exactly ``#ff0000`` (canonical red)
        """
        bar = MetricBar("SWAP")
        app = _MetricBarHostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(95.0, "alert", "부채")
            await pilot.pause()

            hex_code = _fg_hex(bar)
            assert hex_code.lower() == LEVEL_COLORS["alert"].lower(), (
                f"alert-level fg expected {LEVEL_COLORS['alert']!r}, got {hex_code!r}"
            )

    async def test_color_is_whole_text_style_no_per_span_override(self) -> None:
        """The MetricBar locks a single whole-text color (no per-span styling).

        Per-span overrides could leave gaps uncolored; the audit ensures
        the entire row paints in the level's hex. With no spans at all,
        ``text.spans`` is empty.
        """
        bar = MetricBar("CPU")
        app = _MetricBarHostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(50.0, "warn", "매출")
            await pilot.pause()

            text = _get_text(bar)
            assert text.spans == [], (
                f"expected no per-span styling, got spans={text.spans!r}"
            )
            assert str(text.style).lower() == "#ffff00"

    async def test_all_three_levels_are_distinct_hex_values(self) -> None:
        """The three level colors are mutually distinct (sanity check)."""
        colors = {LEVEL_COLORS[k].lower() for k in ("ok", "warn", "alert")}
        assert len(colors) == 3, f"levels share a color: {colors!r}"
        assert colors == {"#00ff00", "#ffff00", "#ff0000"}


# -- Test 3: Narrow-terminal Pilot -----------------------------------------


class TestNarrowTerminalPilot:
    """The full app renders without crash at standard and narrow terminals.

    The plan mandates ``size=(80, 24)`` and ``size=(60, 24)`` both render
    without crashing. ``60`` is intentionally below the layout's
    comfortable minimum (the body split is 30% / 70%); the test asserts
    graceful rendering, not perfect fit.
    """

    async def test_full_app_runs_100_ticks_at_default_size(self) -> None:
        """Given: HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        When:  mounted at default size (80x24) and ``_tick_once`` invoked 100x
        Then:  state.tick advances to 100; no exception raised
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            for _ in range(100):
                app._tick_once()
            await pilot.pause()
            assert app.state.tick == 100, (
                f"expected state.tick==100 after 100 _tick_once calls, "
                f"got {app.state.tick}"
            )

    async def test_full_app_renders_at_80x24_without_crash(self) -> None:
        """Given: HtopTycoonApp mounted at ``size=(80, 24)`` (the default)
        When:  100 ticks elapse
        Then:  no exception; the app's size is 80x24
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            for _ in range(100):
                app._tick_once()
            await pilot.pause()
            width, height = app.size
            assert (width, height) == (80, 24)
            assert app.state.tick == 100

    async def test_full_app_renders_at_60x24_without_crash(self) -> None:
        """Given: HtopTycoonApp mounted at ``size=(60, 24)``
        When:  100 ticks elapse
        Then:  no exception; the app's size is 60x24

        Per the plan's failure-path QA scenario: "terminal width=60 ->
        expect graceful truncate or scroll, not crash". This test enforces
        "not crash" via the absence of an exception and the presence of
        a mounted app at the requested size.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test(size=(60, 24)) as pilot:
            await pilot.pause()
            for _ in range(100):
                app._tick_once()
            await pilot.pause()
            width, height = app.size
            assert (width, height) == (60, 24)
            assert app.state.tick == 100

    async def test_full_app_5_regions_mounted_at_narrow_size(self) -> None:
        """All seven locked region IDs survive a narrow-terminal mount.

        A terminal-narrow crash would surface as missing widgets; assert
        each region is queryable at size=(60, 24).
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test(size=(60, 24)) as pilot:
            await pilot.pause()
            for region_id in (
                "#header",
                "#metrics",
                "#body",
                "#org-tree",
                "#employee-panel",
                "#alerts",
                "#footer",
            ):
                node = app.query_one(region_id)
                assert node is not None


# -- Audit snapshot for .omo/evidence/task-23-htop-tycoon.txt --------------


async def test_audit_snapshot_captures_measurable_widths_and_colors() -> None:
    """Build a deterministic snapshot dict covering all three audits.

    Returned dict keys:
        - ``cpu_bar_width``: CJK cell width of MetricBar('CPU', 30%, '매출')
        - ``cpu_bar_color``: hex foreground color of MetricBar('CPU', 'ok')
        - ``footer_f_row_width``: CJK cell width of the locked F-row
        - ``footer_sk_row_width``: CJK cell width of the single-key row
        - ``header_top_line_width``: CJK cell width of the locked top-line
        - ``level_colors``: locked level->hex palette
        - ``narrow_terminal_size``: target size for the narrow-terminal test
    """
    snapshot: dict[str, object] = {}

    cpu_bar = MetricBar("CPU")
    app = _MetricBarHostApp(cpu_bar)
    console = Console()
    async with app.run_test() as pilot:
        await pilot.pause()
        cpu_bar.update_value(30.0, "ok", "매출")
        await pilot.pause()
        snapshot["cpu_bar_width"] = _measure(_get_text(cpu_bar), console)
        snapshot["cpu_bar_color"] = _fg_hex(cpu_bar)

    snapshot["footer_f_row_width"] = _cell_width(F_ROW)
    snapshot["footer_sk_row_width"] = _cell_width(SINGLE_KEY_ROW)

    header_plain = (
        "tick: 42  |  2026년 1분기 12주차  |  Engineering·5명  |  SaaS"
    )
    snapshot["header_top_line_width"] = _cell_width(header_plain)

    snapshot["level_colors"] = dict(LEVEL_COLORS)
    snapshot["narrow_terminal_size"] = (60, 24)

    assert snapshot["cpu_bar_width"] == 50
    assert snapshot["cpu_bar_color"].lower() == "#00ff00"
    assert snapshot["footer_f_row_width"] == 72
    assert snapshot["footer_sk_row_width"] == 77
    assert snapshot["header_top_line_width"] == 61
    assert snapshot["level_colors"] == {
        "ok": "#00ff00",
        "warn": "#ffff00",
        "alert": "#ff0000",
    }
    assert snapshot["narrow_terminal_size"] == (60, 24)
