"""OrgTree widget — htop-style department tree with employee roster."""

from __future__ import annotations

from collections import defaultdict
from typing import ClassVar

from textual.widgets import Tree

from htop_tycoon.domain import CompanyState, Department, Employee
from htop_tycoon.domain.enums import Job
from htop_tycoon.ui.i18n import DEPT_KO, JOB_KO

ZOMBIE_THRESHOLD: int = 20


def nice_value(job: Job, level: int) -> str:
    """htop-style 'nice value' — job tier name + numeric level."""
    return f"{JOB_KO.get(job.value, job.value)} {level}"


def _employee_label(emp: Employee) -> str:
    marker = " [좀비]" if emp.satisfaction < ZOMBIE_THRESHOLD else ""
    body = (
        f"{emp.name} | {nice_value(emp.job, emp.level)} "
        f"| 만족도:{emp.satisfaction}% | {emp.salary}/월{marker}"
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
        super().__init__(f"회사 ({len(state.employees)}명)")
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
            dept_ko = DEPT_KO.get(dept.value, dept.value)
            dept_label = f"{dept_ko} ({len(employees)}명)"
            dept_node = self.root.add(dept_label)
            dept_node.expand()
            for emp in sorted(employees, key=lambda e: e.name):
                dept_node.add_leaf(_employee_label(emp), data=str(int(emp.id)))

