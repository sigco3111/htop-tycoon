"""OrgTree widget — htop-style department tree with employee roster.

Phase 2C. Groups CompanyState.employees by Department, shows each
employee with their nice_value (job + level), satisfaction, salary,
and a zombie flag when satisfaction < 20. Zombies get Rich markup
[error]...[/error] for red coloring.
"""

from __future__ import annotations

from collections import defaultdict
from typing import ClassVar

from textual.widgets import Tree

from htop_tycoon.domain import CompanyState, Department, Employee
from htop_tycoon.domain.enums import Job

ZOMBIE_THRESHOLD: int = 20


def nice_value(job: Job, level: int) -> str:
    """htop-style 'nice value' — job tier name + numeric level."""
    return f"{job.value} {level}"


def _employee_label(emp: Employee) -> str:
    marker = " [Z]" if emp.satisfaction < ZOMBIE_THRESHOLD else ""
    body = (
        f"{emp.name} | {nice_value(emp.job, emp.level)} "
        f"| sat:{emp.satisfaction}% | {emp.salary}/mo{marker}"
    )
    if emp.satisfaction < ZOMBIE_THRESHOLD:
        return f"[error]{body}[/error]"
    return body


class OrgTree(Tree[str]):
    """htop-style department tree, grouped by Department, leaves per employee."""

    DEFAULT_CSS: ClassVar[str] = """
    OrgTree {
        height: 1fr;
        background: $background;
        color: $primary;
        padding: 0 1;
    }
    """

    def __init__(self, state: CompanyState) -> None:
        super().__init__(f"Company ({len(state.employees)} employees)")
        self._state = state
        self._render_tree()

    def _render_tree(self) -> None:
        self.root.expand()
        by_dept: dict[Department, list[Employee]] = defaultdict(list)
        for emp in self._state.employees.values():
            by_dept[emp.dept].append(emp)

        for dept in Department:
            employees = by_dept.get(dept, [])
            if not employees:
                continue
            dept_label = f"{dept.value} ({len(employees)})"
            dept_node = self.root.add(dept_label)
            dept_node.expand()
            for emp in sorted(employees, key=lambda e: e.name):
                dept_node.add_leaf(_employee_label(emp), data=str(int(emp.id)))
