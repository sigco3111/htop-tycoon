"""S3+ contract: app boots with mock_state, MetricBar renders 4 quality axes.

Pilot test for Phase 2D. Adds MetricBar assertions on top of Phase 2C
OrgTree contract. All header/OrgTree/footer strings still required —
backward compat guard.
"""

from __future__ import annotations

from pathlib import Path

from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state

EXPECTED_HEADER: tuple[str, ...] = (
    "Year 1",
    "Cash $100,000",
    "Fans 0",
    "Strategy: Balanced",
)

EXPECTED_EMPLOYEE_NAMES: tuple[str, ...] = (
    "Ada",
    "Bob",
    "Carol",
    "Dave",
    "Eve",
    "Frank",
)

EXPECTED_DEPT_LABELS: tuple[str, ...] = ("DEV", "ART", "SOUND", "QA")

EXPECTED_METRIC_AXES: tuple[str, ...] = ("FUN", "GRAPHICS", "SOUND", "ORIGINAL")

EXPECTED_METRIC_VALUES: tuple[str, ...] = ("60", "40", "30", "50")

EXPECTED_FOOTER: tuple[str, ...] = (
    "F1도움",
    "F2저장",
    "F3검색",
    "F5트리",
    "F7승진",
    "F9해고",
    "H고용",
    "n새게임",
    "s전략",
    "d자동",
    "Speed 1x",
    "Auto OFF",
)

ALL_EXPECTED_STRINGS: tuple[str, ...] = (
    *EXPECTED_HEADER,
    *EXPECTED_EMPLOYEE_NAMES,
    *EXPECTED_DEPT_LABELS,
    "LEAD",
    "[Z]",
    "$",
    *EXPECTED_METRIC_AXES,
    *EXPECTED_METRIC_VALUES,
    *EXPECTED_FOOTER,
)

SCREENSHOT_DIR: str = "docs/screenshots"
SCREENSHOT_NAME: str = "phase2d_metric_bar.svg"
TEST_SCREEN_SIZE: tuple[int, int] = (120, 40)


def _normalize_svg(svg: str) -> str:
    return (
        svg.replace("&#160;", " ")
        .replace("&#x2588;", "█")
        .replace("&#x2591;", "░")
        .replace("&#9608;", "█")
        .replace("&#9617;", "░")
    )


async def test_metric_bar_screenshot() -> None:
    """App boots with mock_state, MetricBar + OrgTree + header/footer render."""
    app = HtopTycoonApp(state=mock_state())

    async with app.run_test(size=TEST_SCREEN_SIZE) as pilot:
        await pilot.pause()
        svg_path = app.save_screenshot(
            filename=SCREENSHOT_NAME,
            path=SCREENSHOT_DIR,
        )

    svg_file = Path(svg_path)
    assert svg_file.exists(), f"Screenshot not saved at {svg_file}"

    raw = svg_file.read_text(encoding="utf-8")
    content = _normalize_svg(raw)
    missing = [s for s in ALL_EXPECTED_STRINGS if s not in content]

    has_bar_char = "█" in content or "░" in content
    assert has_bar_char, "No filled/empty bar characters in SVG"

    assert not missing, (
        f"Screenshot is missing {len(missing)} expected string(s):\n"
        + "\n".join(f"  - {s!r}" for s in missing)
        + f"\nScreenshot saved at: {svg_file}"
    )
