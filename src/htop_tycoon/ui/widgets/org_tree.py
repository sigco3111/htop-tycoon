"""htop_tycoon.ui.widgets.org_tree — OrgTree widget (T18).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 471-480:

- ``class OrgTree(textual.widgets.Tree)`` shows the company as root,
  departments as children, and employees as grandchildren.
- Default state is COLLAPSED: only the root and dept names are visible;
  employee grandchildren are hidden (matches the htop default).
- The ``t`` keypress toggles expand/collapse of all dept subtrees via
  ``toggle_expand_all()``. T18 declares the binding on the widget so the
  behavior is testable in isolation; T24-T25 will add the same binding at
  the App level (the widget-level binding is a layered default that child
  widgets override per Textual's binding-resolution rules).
- Cursor arrows + Enter are inherited from ``Tree`` (no custom logic).
- ``action_select_employee(employee_id)`` is a documented hook. The body is
  intentionally a no-op for T18 — T25 will replace it with an
  ``EventBus.publish`` call when the App-level binding is wired.

Anti-patterns avoided:

- No direct mutation of ``self.state``. The widget receives a ``GameState``
  snapshot and only reads from it.
- No ``time.sleep`` (blocks the Textual event loop).
- No bare ``random.*`` calls (no RNG flows in this widget).
- No magic numbers: dept/employee labels are sourced from the state, not
  hardcoded strings.
"""

from __future__ import annotations

from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from htop_tycoon.domain.dept import Department
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.state import EmployeeId, GameState

__all__ = ["OrgTree"]


# The "t" key expands or collapses all dept subtrees. ``show=False`` keeps
# the key out of the help bar (htop-style footer is configured in T22).
_TOGGLE_BINDING: Binding = Binding(
    key="t",
    action="toggle_expand_all",
    description="Toggle expand/collapse all departments",
    show=False,
)


# Tree nodes carry either a Department (dept level) or an Employee (leaf
# level); the parameter is the union of both. ``None`` is excluded because
# every node in this widget has a payload.
_TreeData = Department | Employee


class OrgTree(Tree[_TreeData]):
    """Hierarchical company org view: company → departments → employees.

    The tree is read-only: it renders a ``GameState`` snapshot without
    mutating engine state. Selection (Enter) is delegated to the inherited
    ``Tree.NodeSelected`` message; downstream consumers (T25 bindings) call
    ``action_select_employee(employee_id)`` to publish to the EventBus.

    Class attributes:

    - ``BINDINGS``: declares ``t`` → ``toggle_expand_all`` so the widget is
      self-driving in tests; T24-T25 will add the same binding at the App
      level (Textual resolves child-widget bindings first).

    Construction:

    - ``state``: a ``GameState`` snapshot. The widget reads from it but does
      not retain a mutable reference (the state is effectively frozen per
      the engine contract).
    - ``name``/``id``/``classes``/``disabled``: forwarded to ``Tree`` for
      layout/CSS parity with the other T17-T22 widgets.
    """

    # Match the parent's declared BINDINGS type so mypy accepts the
    # narrower list-of-Binding override.
    BINDINGS: ClassVar[list[BindingType]] = [_TOGGLE_BINDING]

    def __init__(
        self,
        state: GameState,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize the tree with the company hierarchy from ``state``.

        Given: a ``GameState`` snapshot
        When:  ``OrgTree(state)`` is constructed
        Then:  ``self.root`` is labeled with the company name, dept children
               are added (collapsed by default), and each dept has its
               employee members as grandchildren (also collapsed by default).
        """
        super().__init__(state.company.name, name=name, id=id, classes=classes, disabled=disabled)
        # Stash the state for downstream handlers that need to look up an
        # employee (e.g. ``action_select_employee``). The widget MUST NOT
        # mutate this object — the engine is the sole writer.
        self._state: GameState = state
        self._build_hierarchy()
        # Textual Tree shows the root label but hides its children by default;
        # expand the root so dept rows are visible per the spec
        # ("root + dept names"). Employee grandchildren stay hidden (added
        # with ``expand=False``).
        self.root.expand()

    # ---- build ----

    def _build_hierarchy(self) -> None:
        """Populate the tree: company (root) > departments > employees.

        Departments are inserted in the iteration order of
        ``state.departments`` (insertion order is preserved by ``dict``).
        Each dept is added with ``expand=False``; each employee leaf is
        added with ``expand=False``. The root is implicitly shown by
        ``Tree(label=...)``; its expansion state is the widget's
        ``show_root`` default (True).
        """
        # Defensive: if the state has no departments, the tree renders just
        # the root (matches the QA failure path).
        for dept_id, dept_obj in self._state.departments.items():
            # Type narrowing: state.departments is dict[DepartmentId, Any]
            # to avoid the circular import on Department; we narrow here.
            assert isinstance(dept_obj, Department), (
                f"state.departments[{dept_id!r}] must be Department, "
                f"got {type(dept_obj).__name__}"
            )
            dept_label = f"{dept_obj.type.value} ({len(dept_obj.employee_ids)})"
            dept_node: TreeNode[_TreeData] = self.root.add(
                dept_label, data=dept_obj, expand=False
            )
            for emp_id in dept_obj.employee_ids:
                emp = self._state.employees.get(emp_id)
                # Skip a missing employee rather than crashing — engine
                # invariants keep these aligned, but the widget stays
                # defensive against transient desyncs.
                if not isinstance(emp, Employee):
                    continue
                emp_label = f"{emp.name} [t{emp.tier} s{emp.skill}]"
                dept_node.add_leaf(emp_label, data=emp)

    # ---- public hook (T25 will replace body) ----

    def action_select_employee(self, employee_id: EmployeeId) -> None:
        """Hook fired when the user selects an employee (Enter on a leaf).

        For T18 the body is intentionally a no-op so the widget can be
        imported and tested in isolation. T25 will replace this body with
        a call to ``self._event_bus.publish(...)`` (or equivalent) to emit
        a selection event. The method exists today so the public surface
        is locked and tests can confirm the hook is callable.

        Given: an ``EmployeeId`` (the engine-side identifier, not the
               node's display label)
        When:  T25's binding handler routes Enter on a leaf to this method
        Then:  (T18) the call is a no-op; (T25+) an event is published
        """
        # Local import to keep the import-time surface stable and avoid
        # a circular import on the engine events module.
        del employee_id  # unused for T18; consumed by T25
        return None

    # ---- toggle (t key) ----

    def action_toggle_expand_all(self) -> None:
        """Textual action invoked by the ``t`` binding.

        Delegates to the public ``toggle_expand_all()`` so the toggle
        behavior is testable without going through the keypress pipeline.
        """
        self.toggle_expand_all()

    def toggle_expand_all(self) -> None:
        """Expand all dept subtrees if all are collapsed; else collapse all.

        Toggles the expansion state of every immediate dept child of the
        root. This intentionally diverges from ``Tree.action_toggle_expand_all``
        (which operates on the cursor's siblings) so the ``t`` key has a
        stable, global effect regardless of where the cursor sits.

        No-op when the company has no departments.
        """
        dept_nodes: list[TreeNode[_TreeData]] = list(self.root.children)
        if not dept_nodes:
            return
        if all(node.is_collapsed for node in dept_nodes):
            for node in dept_nodes:
                node.expand()
        else:
            for node in dept_nodes:
                node.collapse()
