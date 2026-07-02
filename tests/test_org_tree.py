"""Tests for OrgTree.update_state — preserves cursor and expand state across refreshes."""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Department,
    Employee,
    EmployeeId,
    Job,
    Money,
)
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.widgets.org_tree import OrgTree


def _emp(eid: int, name: str = "E", satisfaction: int = 80, dept: Department = Department.DEV) -> Employee:
    return Employee(
        id=EmployeeId(eid),
        name=f"{name}{eid}",
        job=Job.JUNIOR,
        level=2,
        salary=Money(200_00),
        satisfaction=satisfaction,
        dept=dept,
    )


def _find_node_by_data(tree: OrgTree, data: str):
    for node in tree._tree_nodes.values():
        if node.data is not None and str(node.data) == data:
            return node
    return None


def test_update_state_preserves_cursor_on_same_employee() -> None:
    """update_state 후에도 같은 직원에 cursor 유지."""
    state = mock_state(speed=0)
    tree = OrgTree(state)
    ada_node = _find_node_by_data(tree, "1")
    assert ada_node is not None
    tree._cursor_node = ada_node

    new_state = state
    tree.update_state(new_state)

    cursor_node = tree._cursor_node
    assert cursor_node is not None
    assert str(cursor_node.data) == "1"


def test_update_state_preserves_expand_state() -> None:
    """update_state 후에도 부서 expand 상태 유지."""
    state = mock_state(speed=0)
    tree = OrgTree(state)
    tree.root.collapse()
    assert tree.root.is_expanded is False

    tree.update_state(state)

    assert tree.root.is_expanded is False, "expand 상태가 reset되면 안 됨"


def test_update_state_refreshes_employee_satisfaction_label() -> None:
    """update_state 후 직원 label이 새 satisfaction 반영."""
    state = mock_state(speed=0)
    tree = OrgTree(state)

    new_state = state.add_employee(_emp(99, "New", satisfaction=42, dept=Department.DEV))
    tree.update_state(new_state)

    new_node = _find_node_by_data(tree, "99")
    assert new_node is not None
    assert "New99" in str(new_node.label)
    assert "42" in str(new_node.label)


def test_update_state_adds_new_employee() -> None:
    state = mock_state(speed=0)
    tree = OrgTree(state)
    initial_leaves = sum(1 for n in tree._tree_nodes.values() if n.data)

    new_state = state.add_employee(_emp(50, "Fifty", dept=Department.QA))
    tree.update_state(new_state)

    assert _find_node_by_data(tree, "50") is not None
    leaves_after = sum(1 for n in tree._tree_nodes.values() if n.data)
    assert leaves_after == initial_leaves + 1


def test_update_state_removes_terminated_employee() -> None:
    state = mock_state(speed=0)
    tree = OrgTree(state)
    assert _find_node_by_data(tree, "5") is not None

    eve_id = EmployeeId(5)
    new_state = state.remove_employee(eve_id)
    tree.update_state(new_state)

    assert _find_node_by_data(tree, "5") is None