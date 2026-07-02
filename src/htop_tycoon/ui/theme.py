"""Terminal-green htop theme — phosphor-on-black aesthetic.

The primary hex `#39ff14` is a CRT-phosphor green used in classic terminal
emulators and matches the htop theme. Secondary/accent reuse the same hue
to keep the chrome visually unified. Background is near-black for contrast.
"""

from __future__ import annotations

from textual.theme import Theme

# Canonical phosphor-green hex. Single source of truth for the theme.
TERMINAL_GREEN: str = "#39ff14"
PHOSPHOR_BACKGROUND: str = "#0a0a0a"
PHOSPHOR_FOREGROUND: str = "#39ff14"
PHOSPHOR_WARNING: str = "#ffaa00"
PHOSPHOR_ERROR: str = "#ff5555"
PHOSPHOR_SUCCESS: str = "#39ff14"

THEME_NAME: str = "htop-tycoon"


class HtopTycoonTheme(Theme):
    """Single source of truth for the app's phosphor-green palette."""

    def __init__(self) -> None:
        super().__init__(
            name=THEME_NAME,
            primary=TERMINAL_GREEN,
            secondary=TERMINAL_GREEN,
            accent=TERMINAL_GREEN,
            background=PHOSPHOR_BACKGROUND,
            foreground=PHOSPHOR_FOREGROUND,
            warning=PHOSPHOR_WARNING,
            error=PHOSPHOR_ERROR,
            success=PHOSPHOR_SUCCESS,
        )
