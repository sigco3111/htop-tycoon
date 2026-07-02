"""S3 contract: app boots, renders htop chrome, SVG screenshot captures it.

This is the integration test that ties together theme + app + Header + Footer.
It uses Textual's Pilot harness (`app.run_test()`) so it works in headless
environments without a real TTY, and `app.save_screenshot()` to dump the
rendered terminal as SVG.

We then read the SVG as text and grep for every expected string — if the
rendering pipeline ate any text (e.g. CJK truncation, wrong widget), the
assertion fails with a clear "Missing strings" message.

Two normalization steps on the SVG before comparison:
- Decode `&#160;` (non-breaking space) back to ASCII space. Textual/Rich
  uses NBSP in SVG output to prevent line-breaking at spaces.
- Run at 120x30 so all Footer widgets (F-keys + secondary + Speed + Auto)
  fit without truncation. Default 80x24 is too narrow for our chrome.
"""

from __future__ import annotations

import re
from pathlib import Path

from htop_tycoon.ui.app import HtopTycoonApp

EXPECTED_HEADER_LABELS: tuple[str, ...] = (
    "1년차",
    "자금 $100,000",
    "팬 0명",
    "전략: 균형",
)

EXPECTED_FOOTER_F_KEYS: tuple[str, ...] = (
    "F1도움",
    "F2저장",
    "F3검색",
    "F5트리",
    "F7승진",
    "F8로드",
    "F9해고",
)

EXPECTED_FOOTER_SECONDARY: tuple[str, ...] = (
    "H고용",
    "n새게임",
    "s전략",
    "d자동",
)

EXPECTED_FOOTER_STATUS: tuple[str, ...] = (
    "속도 정지",
    "자동 OFF",
)

ALL_EXPECTED_STRINGS: tuple[str, ...] = (
    *EXPECTED_HEADER_LABELS,
    *EXPECTED_FOOTER_F_KEYS,
    *EXPECTED_FOOTER_SECONDARY,
    *EXPECTED_FOOTER_STATUS,
)

SCREENSHOT_DIR: str = "docs/screenshots"
SCREENSHOT_NAME: str = "phase1_boot.svg"
TEST_SCREEN_SIZE: tuple[int, int] = (120, 30)


def _normalize_svg(svg: str) -> str:
    return svg.replace("&#160;", " ")


async def test_boot_screenshot() -> None:
    """App boots, SVG is saved, all expected strings are present in <text> nodes."""
    app = HtopTycoonApp()

    async with app.run_test(size=TEST_SCREEN_SIZE) as pilot:
        await pilot.pause()
        svg_path = app.save_screenshot(
            filename=SCREENSHOT_NAME,
            path=SCREENSHOT_DIR,
        )

    svg_file = Path(svg_path)
    assert svg_file.exists(), f"Screenshot not saved at {svg_file}"
    assert svg_file.suffix == ".svg", f"Expected .svg, got {svg_file.suffix}"

    raw = svg_file.read_text(encoding="utf-8")
    content = _normalize_svg(raw)
    missing = [s for s in ALL_EXPECTED_STRINGS if s not in content]

    # Also re-check for any XML entities we forgot to normalize (debugging aid).
    leftover_entities = set(re.findall(r"&#\d+;", raw)) - {"&#160;"}

    assert not missing, (
        f"Screenshot is missing {len(missing)} expected string(s):\n"
        + "\n".join(f"  - {s!r}" for s in missing)
        + f"\nLeftover XML entities: {sorted(leftover_entities) or 'none'}"
        + f"\nScreenshot saved at: {svg_file}"
    )
