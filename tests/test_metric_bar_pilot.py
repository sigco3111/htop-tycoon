"""Tests for T17: MetricBar widget (CPU/메모리/스왑) with htop color theme.

Locks the contract from .omo/plans/htop-tycoon.md line 458-467:

- class MetricBar(textual.widgets.Static) rendering a horizontal bar
  (block-full filled, light-shade empty) with width 30
- Color from level: ok=green (#00ff00), warn=yellow (#ffff00),
  alert=red (#ff0000) on black bg
- Label format: CPU[매출]  BAR  XX%  level
- Three instances stacked vertically (CPU, MEM, SWAP)
- update_value(pct: float, level: Literal["ok", "warn", "alert"],
  label_ko: str) -> None method
- Pilot test confirms 3 bars render with correct color codes for
  ok/warn/alert levels
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.color import Color
from rich.text import Text
from textual.app import App, ComposeResult

from htop_tycoon.ui.widgets.metric_bar import BAR_WIDTH, MetricBar

if TYPE_CHECKING:
    pass


# -- Test host app ----------------------------------------------------------


class _HostApp(App[None]):
    """Minimal host app for testing MetricBar widgets via Pilot."""

    def __init__(self, *bars: MetricBar) -> None:
        super().__init__()
        self._bars = bars

    def compose(self) -> ComposeResult:
        yield from self._bars


def _get_text(bar: MetricBar) -> Text:
    """Return the underlying Rich ``Text`` renderable for the bar.

    ``Static.renderable`` is a property in Textual 0.86+ that returns
    the parsed renderable (a ``Text`` for our widget). We bypass
    ``bar.render()`` because that returns a ``RichVisual`` wrapper
    (Textual's new visual pipeline) whose ``spans`` are not directly
    accessible.
    """
    return bar.renderable  # type: ignore[no-any-return,return-value]


def _has_fg_color(bar: MetricBar, hex_code: str) -> bool:
    """True if the bar's renderable uses the given fg color.

    When the widget builds a ``Text(body, style=hex_code)``, the style is
    stored on the Text as a whole (no per-character spans), and
    ``text.style`` returns the string ``"#RRGGBB"``. We compare the
    hex_code directly. Falls back to per-span check for future-proofing.
    """
    text = _get_text(bar)
    style_str = str(text.style)
    if style_str.lower() == hex_code.lower():
        return True
    expected = Color.parse(hex_code)
    for span in text.spans:
        if span.style is not None and span.style.color is not None:
            if span.style.color == expected:
                return True
    return False


def _plain(bar: MetricBar) -> str:
    """Return the bar's renderable as a plain string (no markup/colors)."""
    return _get_text(bar).plain


# -- Module surface ---------------------------------------------------------


def test_metric_bar_module_exposes_class() -> None:
    """The metric_bar module is importable and exposes MetricBar."""
    import htop_tycoon.ui.widgets.metric_bar as mod

    assert hasattr(mod, "MetricBar")


def test_metric_bar_is_static_subclass() -> None:
    """MetricBar subclasses textual.widgets.Static (Textual widget contract)."""
    from textual.widgets import Static

    assert issubclass(MetricBar, Static)


def test_bar_width_constant_is_30() -> None:
    """The locked bar width is exactly 30 chars (htop-like, not too wide)."""
    assert BAR_WIDTH == 30


# -- update_value contract --------------------------------------------------


def test_metric_bar_init_does_not_raise() -> None:
    """MetricBar("CPU") constructs without error and exposes a renderable."""
    bar = MetricBar("CPU")
    assert bar is not None
    assert bar.render() is not None


# -- Bar width and format ---------------------------------------------------


class TestMetricBarFormat:
    """The rendered bar is exactly 30 chars wide and follows the locked format."""

    async def test_bar_width_is_30_at_50_percent(self) -> None:
        """Given: MetricBar("CPU") with update_value(50.0, "ok", "매출")
        When: rendered via Pilot
        Then: the bar portion is exactly 30 chars (15 filled + 15 empty)
        """
        bar = MetricBar("CPU")
        app = _HostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(50.0, "ok", "매출")
            await pilot.pause()

            plain = _plain(bar)
            # Format: "NAME[label_ko]  BAR  XX%  level" (2 spaces between).
            parts = plain.split("  ")
            assert len(parts) == 4
            bar_part = parts[1]
            assert len(bar_part) == 30
            assert bar_part == "█" * 15 + "░" * 15

    async def test_label_format_includes_all_fields(self) -> None:
        """Given: MetricBar("CPU") with update_value(50.0, "ok", "매출")
        When: rendered via Pilot
        Then: plain text contains "CPU[매출]", "50%", "ok"
        """
        bar = MetricBar("CPU")
        app = _HostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(50.0, "ok", "매출")
            await pilot.pause()

            plain = _plain(bar)
            assert "CPU[매출]" in plain
            assert "50%" in plain
            assert "ok" in plain

    async def test_filled_count_scales_with_pct(self) -> None:
        """Given: MetricBar with various pct values (0, 25, 100)
        When: rendered via Pilot
        Then: filled = int(pct/100 * 30), empty = 30 - filled
        """
        bar = MetricBar("CPU")
        app = _HostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            for pct, expected_filled in [(0.0, 0), (25.0, 7), (100.0, 30)]:
                bar.update_value(pct, "ok", "매출")
                await pilot.pause()
                plain = _plain(bar)
                bar_part = plain.split("  ")[1]
                expected = "█" * expected_filled + "░" * (30 - expected_filled)
                assert bar_part == expected, (
                    f"pct={pct} expected {expected_filled} filled, got {bar_part!r}"
                )

    async def test_mem_and_swap_names(self) -> None:
        """Given: MetricBar("MEM") and MetricBar("SWAP")
        When: rendered via Pilot
        Then: their names appear in the plain text output
        """
        mem = MetricBar("MEM")
        swap = MetricBar("SWAP")
        app = _HostApp(mem, swap)
        async with app.run_test() as pilot:
            await pilot.pause()
            mem.update_value(50.0, "ok", "재고")
            swap.update_value(50.0, "ok", "부채")
            await pilot.pause()
            assert "MEM[재고]" in _plain(mem)
            assert "SWAP[부채]" in _plain(swap)


# -- Colors for each level --------------------------------------------------


class TestMetricBarColors:
    """Each level maps to the locked htop color (ok=green, warn=yellow, alert=red)."""

    async def test_ok_level_renders_green(self) -> None:
        """Given: level="ok"
        When: rendered via Pilot
        Then: the renderable contains fg color #00ff00
        """
        bar = MetricBar("CPU")
        app = _HostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(30.0, "ok", "매출")
            await pilot.pause()

            assert _has_fg_color(bar, "#00ff00")

    async def test_warn_level_renders_yellow(self) -> None:
        """Given: level="warn"
        When: rendered via Pilot
        Then: the renderable contains fg color #ffff00
        """
        bar = MetricBar("MEM")
        app = _HostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(70.0, "warn", "재고")
            await pilot.pause()

            assert _has_fg_color(bar, "#ffff00")

    async def test_alert_level_renders_red(self) -> None:
        """Given: level="alert"
        When: rendered via Pilot
        Then: the renderable contains fg color #ff0000
        """
        bar = MetricBar("SWAP")
        app = _HostApp(bar)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar.update_value(95.0, "alert", "부채")
            await pilot.pause()

            assert _has_fg_color(bar, "#ff0000")


# -- Three bars stacked (the locked composition) ----------------------------


class TestMetricBarComposition:
    """The 3-bar stack (CPU / MEM / SWAP) renders all three with correct colors."""

    async def test_three_bars_render_with_correct_colors(self) -> None:
        """Given: 3 MetricBars (CPU ok=30, MEM warn=70, SWAP alert=95)
        When: mounted via Pilot + updated
        Then: each bar renders with its locked color (green/yellow/red)
        """
        cpu = MetricBar("CPU", id="cpu")
        mem = MetricBar("MEM", id="mem")
        swap = MetricBar("SWAP", id="swap")
        app = _HostApp(cpu, mem, swap)
        async with app.run_test() as pilot:
            await pilot.pause()
            cpu.update_value(30.0, "ok", "매출")
            mem.update_value(70.0, "warn", "재고")
            swap.update_value(95.0, "alert", "부채")
            await pilot.pause()

            assert _has_fg_color(cpu, "#00ff00")
            assert _has_fg_color(mem, "#ffff00")
            assert _has_fg_color(swap, "#ff0000")

    async def test_three_bars_queryable_by_id(self) -> None:
        """Given: 3 MetricBars with IDs cpu/mem/swap
        When: mounted via Pilot
        Then: app.query_one returns each by its locked ID
        """
        cpu = MetricBar("CPU", id="cpu")
        mem = MetricBar("MEM", id="mem")
        swap = MetricBar("SWAP", id="swap")
        app = _HostApp(cpu, mem, swap)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#cpu") is cpu
            assert app.query_one("#mem") is mem
            assert app.query_one("#swap") is swap

    async def test_snapshot_with_thresholds_72_85_40(self) -> None:
        """Snapshot cpu=72, mem=85, swap=40.

        Per T11 level_for (ok<60, warn<85, alert>=85):
            72 -> warn (yellow), 85 -> alert (red), 40 -> ok (green).
        Bar colors: yellow, red, green.
        """
        from htop_tycoon.engine.metrics import MetricsSnapshot, level_for

        snap = MetricsSnapshot(
            cpu_pct=72, mem_pct=85, swap_pct=40, zombie_count=0, level="alert"
        )
        cpu = MetricBar("CPU", id="cpu")
        mem = MetricBar("MEM", id="mem")
        swap = MetricBar("SWAP", id="swap")
        app = _HostApp(cpu, mem, swap)
        async with app.run_test() as pilot:
            await pilot.pause()
            cpu.update_value(float(snap.cpu_pct), level_for(snap.cpu_pct), "매출")
            mem.update_value(float(snap.mem_pct), level_for(snap.mem_pct), "재고")
            swap.update_value(float(snap.swap_pct), level_for(snap.swap_pct), "부채")
            await pilot.pause()

            assert _has_fg_color(cpu, "#ffff00")  # 72 -> warn -> yellow
            assert _has_fg_color(mem, "#ff0000")  # 85 -> alert -> red
            assert _has_fg_color(swap, "#00ff00")  # 40 -> ok -> green

    async def test_snapshot_with_alert_95(self) -> None:
        """Snapshot cpu=95 -> level=alert -> red (the failure-path QA scenario)."""
        from htop_tycoon.engine.metrics import level_for

        cpu = MetricBar("CPU", id="cpu")
        app = _HostApp(cpu)
        async with app.run_test() as pilot:
            await pilot.pause()
            cpu.update_value(95.0, level_for(95), "매출")
            await pilot.pause()

            assert _has_fg_color(cpu, "#ff0000")
