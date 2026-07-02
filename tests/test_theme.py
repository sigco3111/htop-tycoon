"""S2 contract: terminal-green theme registered + applied to the app.

These tests fail until src/htop_tycoon/ui/theme.py exists with primary=#39ff14
and src/htop_tycoon/ui/app.py registers + selects it.
"""

from __future__ import annotations

from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.theme import HtopTycoonTheme

EXPECTED_PRIMARY_HEX: str = "#39ff14"
EXPECTED_THEME_NAME: str = "htop-tycoon"


def test_terminal_green_hex() -> None:
    """Theme primary must be the canonical terminal-green hex used by htop."""
    theme = HtopTycoonTheme()

    assert theme.name == EXPECTED_THEME_NAME, (
        f"Expected theme name {EXPECTED_THEME_NAME!r}, got {theme.name!r}"
    )
    assert theme.primary == EXPECTED_PRIMARY_HEX, (
        f"Expected primary {EXPECTED_PRIMARY_HEX!r}, got {theme.primary!r}"
    )


async def test_app_uses_theme() -> None:
    """HtopTycoonApp must boot with our theme selected (not Textual default)."""
    app = HtopTycoonApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == EXPECTED_THEME_NAME, (
            f"Expected app.theme == {EXPECTED_THEME_NAME!r}, got {app.theme!r}"
        )
        # Theme should appear in available_themes registry.
        theme_names = {t.name for t in app.available_themes.values()}
        assert EXPECTED_THEME_NAME in theme_names, (
            f"Theme {EXPECTED_THEME_NAME!r} not registered. "
            f"Available: {sorted(theme_names)}"
        )


def test_theme_has_dark_foreground() -> None:
    """Foreground must contrast with primary (basic sanity for legibility)."""
    theme = HtopTycoonTheme()

    assert theme.foreground != theme.background, (
        "Foreground must differ from background or text would be invisible"
    )
    # Background is intentionally near-black for the htop-phosphor look.
    assert theme.background is not None
