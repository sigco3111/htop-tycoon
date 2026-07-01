"""htop-tycoon v3.0 — HtopFooter widget (spec §4.1).

Footer renders F-key hints in Korean + speed control (0=정지, 1-4=1x-4x)
+ Auto mode indicator. Renders from ``bindings.registry.BINDINGS``.
"""
from __future__ import annotations

from textual.widget import Widget

from htop_tycoon.bindings.registry import BINDINGS


class HtopFooter(Widget):
    """Spec §4.1: 'Footer bar: F-key hints (Korean) + Auto mode indicator'."""

    DEFAULT_CSS = """
    HtopFooter {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $secondary;
        padding: 0 1;
    }
    """

    def render(self) -> str:
        # Render the F-key labels (compact) + speed legend on the right.
        fkeys = [b for b in BINDINGS if b.key.startswith("F") and b.description]
        legend = " ".join(f"[{b.key}] {b.description}" for b in fkeys[:10])
        # Speed legend (right side, anchored visually at the end)
        speed = "Speed: [0]정지 [1]1x [2]2x [3]3x [4]4x(QA)"
        # Auto indicator
        auto_on = getattr(self.app, "auto_mode", False)
        auto = f"[Auto: {'ON' if auto_on else 'OFF'}]"
        return f"{legend}  {speed}  {auto}"


__all__ = ["HtopFooter"]
