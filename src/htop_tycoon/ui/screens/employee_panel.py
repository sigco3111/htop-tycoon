"""htop-tycoon v3.0 — EmployeePanelScreen (spec §4.1).

Detail modal for a selected employee. Shows full employee info (dept, job,
level, salary, satisfaction) + buttons for promote / demote / fire.

Spec §4.1 keys:
- F7 ] — promote
- F8 [ — demote
- F9 k — fire
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from htop_tycoon.domain import Employee, GameState


class EmployeePanelScreen(ModalScreen[str | None]):
    """Spec §4.1: employee detail modal with promote / demote / fire."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "닫기"),
    ]

    DEFAULT_CSS = """
    EmployeePanelScreen {
        align: center middle;
    }
    #employee-panel {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self, employee: Employee, state: GameState) -> None:
        super().__init__()
        self._employee = employee
        self._state = state

    def compose(self) -> ComposeResult:
        e = self._employee
        with Vertical(id="employee-panel"):
            yield Static(f"[bold]직원: {e.name}[/]")
            yield Static(f"  부서 (Dept): {e.dept.name}")
            yield Static(f"  직업 (Job):  {e.job.name}")
            yield Static(f"  레벨 (Level): {e.level}")
            yield Static(f"  급여 (Salary): {e.salary_daily:,}G/일")
            yield Static(f"  만족도 (Satisfaction): {e.satisfaction:.0%}")
            yield Static(f"  좀비? (Zombie): {'YES' if e.is_unsatisfied else 'no'}")
            yield Static("")
            yield Button("승진 (Promote, F7 ])", id="promote")
            yield Button("감봉 (Demote, F8 [)", id="demote")
            yield Button("해고 (Fire, F9 k)", id="fire")
            yield Static("", id="status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from htop_tycoon.engine import actions as engine_actions
        from htop_tycoon.engine.rng import GameRNG

        eid = self._employee.id
        rng = GameRNG(42)
        if event.button.id == "promote":
            new_state, _events = engine_actions.promote(self._state, rng, employee_id=eid)
            self._state = new_state
            self.dismiss("promoted")
        elif event.button.id == "demote":
            new_state, _events = engine_actions.demote(self._state, rng, employee_id=eid)
            self._state = new_state
            self.dismiss("demoted")
        elif event.button.id == "fire":
            new_state, _events = engine_actions.fire(
                self._state, rng, employee_id=eid, reason="player"
            )
            self._state = new_state
            self.dismiss("fired")

    async def action_dismiss(self, value: str | None = None) -> None:
        self.dismiss(value)


__all__ = ["EmployeePanelScreen"]
