"""htop-tycoon v3.0 — htop-style Textual theme.

A dark theme inspired by the canonical htop color palette: dark gray
background, cyan/blue meters, red for hot/critical, green for normal,
yellow for warning. Spec §4.1: "Korean UI default + htop visual style".
"""
from __future__ import annotations

from textual.theme import Theme

HTOPTYCOON_THEME = Theme(
    name="htoptycoon",
    primary="#00ffaf",
    secondary="#5fafff",
    accent="#5fafff",
    foreground="#e0e0e0",
    background="#0a0e0f",
    surface="#1c2025",
    panel="#1c2025",
    success="#00cc7a",
    warning="#ffcc00",
    error="#ff5555",
    dark=True,
)


__all__ = ["HTOPTYCOON_THEME"]
