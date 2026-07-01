"""htop-tycoon v3.0 — ArchiveScreen (spec §4.1).

Shows a list of past game projects with their final quality / sales.
Read-only — drives off ``state.released_projects()``.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from htop_tycoon.domain import GameState


class ArchiveScreen(ModalScreen[None]):
    """Spec §4.1: 'Archive' — past game results."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "닫기"),
    ]

    DEFAULT_CSS = """
    ArchiveScreen {
        align: center middle;
    }
    #archive {
        width: 80;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        with Vertical(id="archive"):
            yield Static("[bold]보관함 (Archive) — 출시된 게임 목록[/]")
            table: DataTable = DataTable()  # type: ignore[type-arg]
            table.add_columns("Name", "Genre", "Theme", "Progress", "Quality", "Sales")
            for p in self._state.released_projects():
                table.add_row(
                    p.name,
                    p.genre_id,
                    p.theme_id,
                    f"{p.progress_pct:.0f}%",
                    f"{p.current_quality_avg:.1f}",
                    f"{p.sales_total:,}",
                )
            yield table

    async def action_dismiss(self, value: None = None) -> None:
        self.dismiss(value)


__all__ = ["ArchiveScreen"]
