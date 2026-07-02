"""S3+ contract: app boots with mock_state, OrgTree renders 6 employees.

Pilot test for Phase 2C. Runs HtopTycoonApp with mock_state(), captures
SVG, normalizes NBSP → space, asserts all expected strings present.
"""

from __future__ import annotations

from pathlib import Path

from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.mock_state import mock_state

EXPECTED_EMPLOYEE_NAMES: tuple[str, ...] = (
    "Ada",
    "Bob",
    "Carol",
    "Dave",
    "Eve",
    "Frank",
)

EXPECTED_DEPT_LABELS: tuple[str, ...] = (
    "개발",
    "아트",
    "사운드",
    "QA",
)

EXPECTED_FOOTER_LABELS: tuple[str, ...] = (
    "F1도움",
    "F2저장",
    "F3검색",
    "F5트리",
    "F7승진",
    "F8로드",
    "F9해고",
    "H고용",
    "n새게임",
    "s전략",
    "d자동",
    "속도 정지",
    "자동 OFF",
)

EXPECTED_HEADER_LABELS: tuple[str, ...] = (
    "1년차",
    "자금 $100,000",
    "팬 0명",
    "전략: 균형",
)

ALL_EXPECTED_STRINGS: tuple[str, ...] = (
    *EXPECTED_HEADER_LABELS,
    *EXPECTED_EMPLOYEE_NAMES,
    *EXPECTED_DEPT_LABELS,
    "리드",
    "[좀비]",
    "$",
    *EXPECTED_FOOTER_LABELS,
)

SCREENSHOT_DIR: str = "docs/screenshots"
SCREENSHOT_NAME: str = "phase2c_org_tree.svg"
TEST_SCREEN_SIZE: tuple[int, int] = (120, 30)


def _normalize_svg(svg: str) -> str:
    return svg.replace("&#160;", " ")


async def test_org_tree_screenshot() -> None:
    """App boots with mock_state, OrgTree renders 6 employees, SVG captures it."""
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

    assert not missing, (
        f"Screenshot is missing {len(missing)} expected string(s):\n"
        + "\n".join(f"  - {s!r}" for s in missing)
        + f"\nScreenshot saved at: {svg_file}"
    )
