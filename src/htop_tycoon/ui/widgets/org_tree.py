"""OrgTree widget — htop-style department tree with employee roster."""

from __future__ import annotations

from collections import defaultdict
from typing import ClassVar

from textual.widgets import Tree
from textual.widgets.tree import TreeNode

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


def _collect_employee_data(node: TreeNode[str]) -> list[str]:
    """Recursively collect leaf node 'data' attributes (employee IDs as strings)."""
    if node.allow_expand:
        result: list[str] = []
        for child in node.children:
            result.extend(_collect_employee_data(child))
        return result
    if node.data:
        return [str(node.data)]
    return []


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

    def _walk_all_nodes(self):
        """Iterate over every TreeNode in the tree (private API)."""
        return self._tree_nodes.values()

    def _save_cursor(self) -> str | None:
        try:
            node = self.cursor_node
        except Exception:
            return None
        if node is None:
            return None
        return str(node.data) if node.data is not None else None

    def _save_expanded_paths(self) -> tuple[set[str], bool]:
        """Save the set of 'data' attributes of currently-expanded nodes + root state."""
        paths: set[str] = set()
        for node in self._walk_all_nodes():
            if node.is_expanded and node.data:
                paths.add(str(node.data))
        return paths, self.root.is_expanded

    def _restore_cursor(self, target_data: str | None) -> None:
        if target_data is None:
            return
        for node in self._walk_all_nodes():
            if node.data is not None and str(node.data) == target_data:
                self._cursor_node = node
                return

    def _restore_expanded_paths(self, expanded: set[str], root_expanded: bool) -> None:
        if root_expanded:
            self.root.expand()
        else:
            self.root.collapse()
        for node in self._walk_all_nodes():
            if node.data is not None and str(node.data) in expanded:
                node.expand()

    def update_state(self, state: CompanyState) -> None:
        """Refresh tree contents in place, preserving cursor and expand state.

        Without this method, every refresh rebuilds the tree and the user's
        selected node / expanded branches are lost. With it, only labels
        change for surviving employees; new employees get added, removed
        employees get dropped.
        """
        cursor_data = self._save_cursor()
        expanded, root_expanded = self._save_expanded_paths()

        self._state = state
        self.root.label = f"회사 ({len(state.employees)}명)"
        self.root.remove_children()
        self._render_tree()
        self._restore_expanded_paths(expanded, root_expanded)
        self._restore_cursor(cursor_data)

