"""htop-tycoon v3.0 — HtopHeader widget (spec §4.1).

Header bar shows year / cash / fans / strategy indicator. Updates
reactively when the app's bound ``GameState`` changes.
"""
from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget

from htop_tycoon.domain import GameState


class HtopHeader(Widget):
    """Spec §4.1: 'Header bar: Year / Cash / Fans / Strategy indicator'."""

    DEFAULT_CSS = """
    HtopHeader {
        dock: top;
        height: 1;
        background: $surface;
        color: $primary;
        padding: 0 1;
    }
    """

    # Reactive reference to the game state. The app binds this via
    # ``header.state = state`` whenever the simulation ticks.
    state: reactive[GameState | None] = reactive(None, always_update=True)

    def watch_state(self, new_state: GameState | None) -> None:
        """Re-render the widget when the bound state changes."""
        self.refresh()

    def render(self) -> str:
        if self.state is None:
            return "[HtopTycoon v3.0 — booting...]"
        s = self.state
        year = (s.day // 365) + 1
        cash = f"{s.cash:,}G"
        fans = f"{s.fans:,}"
        # Strategy: GameState doesn't yet carry a strategy_name (that's
        # UI state, not domain). Until the Strategy Picker screen sets
        # the active strategy, show "manual" — the UI layer tracks this
        # via its own ``app.active_strategy`` attribute.
        strategy = getattr(self.app, "active_strategy", None) or "manual"
        return (
            f"[bold cyan]htop-tycoon v3.0[/]  "
            f"[white]Year[/][yellow]{year}[/]  "
            f"[white]Cash[/][green]{cash}[/]  "
            f"[white]Fans[/][magenta]{fans}[/]  "
            f"[white]Strategy[/][cyan]{strategy}[/]"
        )


__all__ = ["HtopHeader"]
