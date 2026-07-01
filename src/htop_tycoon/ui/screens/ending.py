"""htop-tycoon v3.0 — EndingScreen (spec §1.4, §4.1).

Summary shown when the game ends. Displays the ending kind (BANKRUPTCY /
VOLUNTARY_SALE / MEGA_HIT / HALL_OF_FAME / SECRET — spec §1.4), the day,
the final cash, the number of released games, and any closing notes.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from htop_tycoon.domain import Ending, GameState

_ENDING_KO: dict[str, str] = {
    "BANKRUPTCY": "파산 (Bankruptcy)",
    "VOLUNTARY_SALE": "자발적 매각 (Voluntary Sale)",
    "MEGA_HIT": "대박 (Mega Hit)",
    "HALL_OF_FAME": "명예의 전당 (Hall of Fame)",
    "SECRET": "비밀: 자사 콘솔 + 메가히트 (Secret)",
}


class EndingScreen(ModalScreen[None]):
    """Spec §1.4 / §4.1: game-over summary screen."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "닫기"),
    ]

    DEFAULT_CSS = """
    EndingScreen {
        align: center middle;
    }
    #ending {
        width: 70;
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
        ending: Ending | None = self._state.ending
        with Vertical(id="ending"):
            if ending is None:
                yield Static("[bold]게임 종료 (Game Over)[/]")
                yield Static("  Ending: (none)")
                yield Static(f"  Day: {self._state.day}")
                yield Static(f"  Cash: {self._state.cash:,}G")
                yield Static(f"  Games released: {len(self._state.released_projects())}")
                yield Static("  Notes: (no ending recorded)")
            else:
                label = _ENDING_KO.get(ending.kind.name, ending.kind.name)
                yield Static(f"[bold]게임 종료 (Game Over) — {label}[/]")
                yield Static(f"  Day: {ending.day}")
                yield Static(f"  Cash at end: {ending.cash_at_end:,}G")
                yield Static(f"  Games released: {ending.games_count}")
                yield Static(f"  Notes: {ending.notes or '(none)'}")
            yield Button("닫기 (Close)", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss(None)

    async def action_dismiss(self, value: None = None) -> None:
        self.dismiss(value)


__all__ = ["EndingScreen"]
