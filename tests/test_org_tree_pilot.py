"""Tests for T18: OrgTree widget — t key toggle, departments + employees.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 471-480:

- ``class OrgTree(textual.widgets.Tree)`` shows the company as root, departments
  as children, and employees as grandchildren.
- Default state is COLLAPSED: only the root and dept names are visible
  (employee grandchildren are hidden). Matches the htop default.
- The ``t`` keypress toggles expand/collapse. For T18 the widget exposes a
  public ``toggle_expand_all()`` method + a ``Binding("t", ...)`` so the test
  can drive the toggle via Pilot. T24-T25 will add the same binding at the
  App level; the widget-level binding is a layered default.
- Cursor arrows + Enter are inherited from ``Tree`` (no custom logic).
- ``action_select_employee(employee_id)`` is exposed as a hook for T25 to
  wire Enter-on-employee to the EventBus. For T18 it is a documented no-op
  stub: the method exists, accepts an ``EmployeeId``, returns ``None``.

The tests use the headless Pilot surface (no TTY) so they run in CI.
"""

from __future__ import annotations

import dataclasses

from textual.app import App

from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.state import DepartmentId, EmployeeId, GameState, new_game
from htop_tycoon.ui.widgets.org_tree import OrgTree

# -- GameState fixture -----------------------------------------------------


def _make_test_state() -> GameState:
    """Build a GameState with 1 Engineering department + 5 employees.

    The fixture is the minimum useful company: one head employee, four
    rank-and-file members, all assigned to the same department. This matches
    the spec's QA scenario: "load fixture with 1 dept + 5 employees".
    """
    employees: dict[EmployeeId, Employee] = {}
    for i in range(5):
        emp = Employee(
            id=EmployeeId(f"emp-{i:03d}"),
            name=f"직원{i}",
            dept_id=DepartmentId("dept-eng"),
            skill=5,
            tier=2,
            salary_per_week=1000,
            satisfaction=80,
            hired_tick=0,
        )
        employees[emp.id] = emp
    dept = Department(
        id=DepartmentId("dept-eng"),
        type=DepartmentType.Engineering,
        head_employee_id=EmployeeId("emp-000"),
        employee_ids=list(employees.keys()),
        founded_tick=0,
        unlocked=True,
    )
    return dataclasses.replace(
        new_game(rng_seed=42),
        departments={dept.id: dept},
        employees=employees,
    )


def _make_empty_state() -> GameState:
    """Build a GameState with NO departments and NO employees.

    Used to lock the failure path: "empty company → tree shows root only".
    """
    return new_game(rng_seed=42)


# -- Pilot host App --------------------------------------------------------


class _OrgTreeHostApp(App[None]):
    """Minimal App that mounts an OrgTree with the given state.

    The widget is focused on mount so key bindings (especially ``t``) are
    delivered to the tree, not the screen.
    """

    def __init__(self, state: object) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> object:
        yield OrgTree(self._state, id="org-tree")

    def on_mount(self) -> None:
        # Focus the tree so key events route to it (not the screen).
        self.query_one(OrgTree).focus()


# -- Tree structure --------------------------------------------------------


class TestOrgTreeStructure:
    """OrgTree builds a 3-level hierarchy: company > dept > employees."""

    async def test_tree_root_label_is_company_name(self) -> None:
        """Given: a GameState with company name
        When: OrgTree is mounted
        Then: the root node's label is the company name
        """
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            assert tree.root.label.plain == "My Company"

    async def test_tree_has_one_child_per_department(self) -> None:
        """Given: 1 department in the state
        When: OrgTree is mounted
        Then: root has exactly 1 child (the dept)
        """
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            assert len(tree.root.children) == 1

    async def test_tree_empty_company_has_no_children(self) -> None:
        """Given: an empty state (no departments)
        When: OrgTree is mounted
        Then: root has no children (failure path: root only)
        """
        state = _make_empty_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            assert len(tree.root.children) == 0

    async def test_dept_node_has_employee_grandchildren(self) -> None:
        """Given: 1 dept with 5 employees
        When: OrgTree is mounted
        Then: the dept node has exactly 5 children (one per employee)
        """
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            dept_node = tree.root.children[0]
            assert len(dept_node.children) == 5

    async def test_employee_node_data_is_employee_instance(self) -> None:
        """Employee leaves carry the underlying ``Employee`` instance via data.

        The binding is the only way for T25 / action handlers to look up
        the ``EmployeeId`` + display fields from the tree node.
        """
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            dept_node = tree.root.children[0]
            first_employee_leaf = dept_node.children[0]
            assert isinstance(first_employee_leaf.data, Employee)
            assert first_employee_leaf.data.id == EmployeeId("emp-000")


# -- Default collapsed state ----------------------------------------------


class TestOrgTreeDefaultCollapsed:
    """The tree starts COLLAPSED: employee grandchildren are not visible.

    Per the spec: "Default state: collapsed (only depts visible — root +
    dept names)". The root must be EXPANDED so the dept rows are visible;
    the dept nodes must be COLLAPSED so the employee grandchildren are
    hidden. Two constraints, both required.
    """

    async def test_root_starts_expanded(self) -> None:
        """Given: any state
        When: OrgTree is mounted
        Then: the root is expanded (so dept rows are visible)
        """
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            assert tree.root.is_expanded

    async def test_dept_starts_collapsed(self) -> None:
        """Given: 1 dept with 5 employees
        When: OrgTree is mounted
        Then: the dept node is collapsed (employees are not visible)
        """
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            dept_node = tree.root.children[0]
            assert dept_node.is_collapsed

    async def test_all_depts_start_collapsed(self) -> None:
        """The "start collapsed" guarantee holds for every dept in the tree."""
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            for dept_node in tree.root.children:
                assert dept_node.is_collapsed


# -- t key toggle (Pilot) --------------------------------------------------


class TestOrgTreeToggleExpandAll:
    """The ``t`` keypress toggles expand/collapse of all dept subtrees."""

    async def test_t_press_expands_all_depts(self) -> None:
        """Given: 1 dept with 5 employees (started collapsed)
        When: the user presses ``t`` once
        Then: every dept is expanded (employees become visible)
        """
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            assert tree.root.children[0].is_collapsed
            await pilot.press("t")
            await pilot.pause()
            for dept_node in tree.root.children:
                assert dept_node.is_expanded

    async def test_second_t_press_collapses_all_depts(self) -> None:
        """Given: tree has been expanded once
        When: the user presses ``t`` again
        Then: every dept is collapsed (employees hidden again)
        """
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            await pilot.press("t")
            await pilot.pause()
            await pilot.press("t")
            await pilot.pause()
            for dept_node in tree.root.children:
                assert dept_node.is_collapsed

    async def test_three_presses_expand_collapse_expand(self) -> None:
        """Triple-toggle sanity: expand / collapse / expand across three presses."""
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            assert tree.root.children[0].is_collapsed
            await pilot.press("t")
            await pilot.pause()
            assert tree.root.children[0].is_expanded
            await pilot.press("t")
            await pilot.pause()
            assert tree.root.children[0].is_collapsed
            await pilot.press("t")
            await pilot.pause()
            assert tree.root.children[0].is_expanded


# -- Public toggle method (callable from bindings) ------------------------


class TestOrgTreeToggleExpandAllMethod:
    """``toggle_expand_all()`` is the public hook the App-level binding calls."""

    async def test_toggle_expand_all_expands_when_all_collapsed(self) -> None:
        """Direct call to ``toggle_expand_all()`` expands when all are collapsed."""
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            tree.toggle_expand_all()
            await pilot.pause()
            assert tree.root.children[0].is_expanded

    async def test_toggle_expand_all_collapses_when_any_expanded(self) -> None:
        """If any dept is expanded, ``toggle_expand_all()`` collapses them all."""
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            # First toggle: expand
            tree.toggle_expand_all()
            await pilot.pause()
            assert tree.root.children[0].is_expanded
            # Second toggle: collapse
            tree.toggle_expand_all()
            await pilot.pause()
            assert tree.root.children[0].is_collapsed

    async def test_toggle_expand_all_on_empty_tree_is_safe(self) -> None:
        """No departments: the method is a safe no-op (does not raise)."""
        state = _make_empty_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            tree.toggle_expand_all()
            await pilot.pause()
            assert len(tree.root.children) == 0


# -- action_select_employee hook (T25 will wire Enter) --------------------


class TestOrgTreeActionSelectEmployee:
    """``action_select_employee`` is the public hook T25 will wire to Enter."""

    def test_action_select_employee_method_exists(self) -> None:
        """The hook method exists on the class and is callable."""
        assert hasattr(OrgTree, "action_select_employee")
        assert callable(OrgTree.action_select_employee)

    async def test_action_select_employee_accepts_employee_id(self) -> None:
        """The hook accepts an ``EmployeeId`` and returns ``None`` (no raise)."""
        state = _make_test_state()
        app = _OrgTreeHostApp(state)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(OrgTree)
            # Should not raise; T25 will replace the body with a bus publish.
            result = tree.action_select_employee(EmployeeId("emp-000"))
            assert result is None


# -- Module surface ---------------------------------------------------------


def test_org_tree_subclasses_textual_tree() -> None:
    """``OrgTree`` is a subclass of ``textual.widgets.Tree``."""
    from textual.widgets import Tree

    assert issubclass(OrgTree, Tree)


def test_org_tree_is_exported_from_widgets_package() -> None:
    """``OrgTree`` is re-exported from ``htop_tycoon.ui.widgets``."""
    from htop_tycoon.ui.widgets import OrgTree as ReExported

    assert ReExported is OrgTree
