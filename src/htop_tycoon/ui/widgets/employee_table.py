"""htop-tycoon v3.0 — EmployeeTable widget (spec §4.1).

Read-only DataTable showing every employee's: name, department, job,
level, salary, satisfaction. Re-renders reactively when the bound state's
employees tuple changes.
"""
from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import DataTable

from htop_tycoon.domain import Department, GameState, JobType


class EmployeeTable(DataTable):  # type: ignore[type-arg]
    """Spec §4.1: employee roster view (F3 search / F4 filter — Wave 6+)."""

    DEFAULT_CSS = """
    EmployeeTable {
        height: 1fr;
    }
    """

    state: reactive[GameState | None] = reactive(None, always_update=True)

    def watch_state(self, _: GameState | None) -> None:
        self._refresh_table()

    def on_mount(self) -> None:
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.clear(columns=True)
        self.add_columns("Name", "Dept", "Job", "Lv", "Salary/d", "Satisfaction", "Zombie?")
        if self.state is None:
            return
        for emp in self.state.employees:
            self.add_row(
                emp.name,
                emp.dept.name if isinstance(emp.dept, Department) else str(emp.dept),
                emp.job.name if isinstance(emp.job, JobType) else str(emp.job),
                str(emp.level),
                f"{emp.salary_daily:,}G",
                f"{emp.satisfaction:.0%}",
                "[red]YES[/]" if emp.is_unsatisfied else "no",
            )


__all__ = ["EmployeeTable"]
