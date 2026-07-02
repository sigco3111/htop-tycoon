"""htop-tycoon v3.0 — htop-style Textual theme.

A dark theme inspired by the canonical htop color palette: near-black
background, terminal-green meters (the iconic #39ff14 neon green used
by classic htop), red for hot/critical, yellow for warning. The previous
version used #5fafff (sky blue) for secondary/accent which read too dark
on dark backgrounds — switched to #39ff14 (bright terminal green) for
legibility. Spec §4.1: "Korean UI default + htop visual style".
"""
from __future__ import annotations

from textual.theme import Theme

HTOPTYCOON_THEME = Theme(
    name="htoptycoon",
    primary="#00ffaf",
    secondary="#39ff14",  # terminal green (was #5fafff sky blue — too dim)
    accent="#39ff14",     # terminal green (was #5fafff sky blue — too dim)
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
