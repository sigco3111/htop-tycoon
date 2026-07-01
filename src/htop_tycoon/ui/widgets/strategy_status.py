"""htop-tycoon v3.0 — StrategyStatus widget (spec §4.1).

Shows the most-recent AI actions emitted by the Strategy Manager during
today's tick. Bound to ``GameState.events`` — renders up to N=20 recent
events with a 0..100 priority ordering (higher = more urgent).
"""
from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

from htop_tycoon.domain import Event, GameState

# Cap on how many recent events to render (full event log is unbounded).
_VISIBLE_LIMIT: int = 20


def _kind_label(kind: str) -> str:
    """Colorize event kind for the status panel."""
    color_map = {
        "tick": "dim",
        "hire": "green",
        "fire": "red",
        "train": "cyan",
        "start_game": "yellow",
        "assign": "cyan",
        "promote": "green",
        "demote": "yellow",
        "change_job": "cyan",
        "award": "green",
        "fan_decay": "dim",
        "console_discontinue": "red",
        "ending": "red bold",
        "milestone": "yellow",
    }
    color = color_map.get(kind, "white")
    return f"[{color}]{kind}[/]"


class StrategyStatus(Static):
    """Spec §4.1: 'StrategyStatus widget (AI action log)'."""

    DEFAULT_CSS = """
    StrategyStatus {
        height: auto;
        max-height: 10;
        background: $surface;
        color: $foreground;
        padding: 0 1;
        border: solid $primary;
    }
    """

    state: reactive[GameState | None] = reactive(None, always_update=True)

    def watch_state(self, _: GameState | None) -> None:
        self.refresh()

    def render(self) -> str:
        if self.state is None:
            return "[dim italic]AI actions log — no events yet[/]"
        # Newest first; spec §4.1: 'higher = rendered earlier in UI lists'
        events: list[Event] = sorted(
            self.state.events,
            key=lambda e: (-e.priority, -e.day),
        )[:_VISIBLE_LIMIT]
        if not events:
            return "[dim italic]AI actions log — no events yet[/]"
        lines: list[str] = ["[bold]AI Actions (most recent first):[/]"]
        for e in events:
            status = e.payload.get("status", "ok") if e.payload else "ok"
            lines.append(
                f"  day={e.day:4d}  {_kind_label(e.kind):20s}  status={status}"
            )
        return "\n".join(lines)


__all__ = ["StrategyStatus"]
