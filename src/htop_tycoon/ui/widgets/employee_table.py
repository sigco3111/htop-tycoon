"""htop_tycoon.ui.widgets.employee_table — EmployeeTable DataTable widget (T19).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 482-491:

- ``class EmployeeTable(textual.widgets.DataTable)`` showing all employees
  (or filtered by dept) with columns: ID, 이름, 부서, 스킬, Tier, 급여, 만족도.
- Default sort: by 스킬 desc.
- ``M`` key sorts by 만족도 -- exposed via ``sort_by_satisfaction()``.
- ``P`` key sorts by 급여 -- exposed via ``sort_by_salary()``.
- ``u`` keypress shows a dept picker overlay (T25 will wire it; for T19, the
  contract is exposed via ``filter_by_department(dept_id)``).

Read-only display; F7/F8/F9 actions fire from bindings (T25). State mutation
is intentionally NOT performed by this widget -- selection is for display only.

The row keys are ``EmployeeId`` strings so tests can assert order via
``get_rows()``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from textual.widgets import DataTable

from htop_tycoon.domain.state import DepartmentId

if TYPE_CHECKING:
    from htop_tycoon.domain.dept import Department
    from htop_tycoon.domain.employee import Employee

# Locked column order. Matches the plan line 483. Labels are Korean per spec.
# We use ``add_column(label, key=...)`` per column because Textual's
# ``add_columns`` helper in 8.2.7 does not auto-unpack tuples -- it forwards
# each arg straight to ``add_column(label, width=None)``.
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("ID", "id"),
    ("이름", "name"),
    ("부서", "dept"),
    ("스킬", "skill"),
    ("Tier", "tier"),
    ("급여", "salary"),
    ("만족도", "satisfaction"),
)

__all__ = ["EmployeeTable"]


class EmployeeTable(DataTable[str]):
    """DataTable widget listing employees with dept filter + sort hooks.

    The widget is constructed eagerly (in ``__init__``) so tests can inspect
    it without going through a Pilot. The constructor populates columns and
    rows in skill-desc order (the locked default).

    State mutation is FORBIDDEN here per AGENTS.md "State boundary" -- this
    widget only reads. F7/F8/F9 actions fire from bindings (T25).

    We parameterize ``DataTable[str]`` because every cell we emit is a
    ``str`` (column labels are text, numeric fields are pre-``str()``-ed).
    ``DataTable[None]`` would force every cell to be ``None`` per the
    TypeVar's invariant and reject our string cells.
    """

    def __init__(
        self,
        *,
        employees: list[Employee],
        departments: dict[DepartmentId, Department],
    ) -> None:
        """Build the table: 7 locked columns + one row per employee (skill-desc).

        Given: ``employees`` (full list) and ``departments`` (id -> Department
               map for label lookup)
        When: ``EmployeeTable(...)`` is constructed
        Then: the table has 7 columns in the locked order and rows in
              skill-desc order; no filter is applied (all employees shown).
        """
        super().__init__()
        # Stash the inputs so subsequent sort/filter calls can rebuild rows
        # without forcing the caller to re-supply them.
        self._all_employees: list[Employee] = list(employees)
        self._departments: dict[DepartmentId, Department] = departments
        # ``_filter_dept_id`` is None = "show all". Locked initial state.
        self._filter_dept_id: DepartmentId | None = None

        # Add the 7 locked columns. ``add_column(label, key=...)`` is the
        # documented stable API; each column gets a stable ColumnKey we can
        # sort by later. ``show_header=True`` is the DataTable default but
        # we lock it explicitly so future refactors can't quietly drop it.
        self.show_header = True
        for label, key in _COLUMNS:
            self.add_column(label, key=key)

        # Populate rows in the locked default order (skill-desc).
        self._populate_rows()

    # -------------------------------------------------------------- public API

    def get_rows(self) -> list[str]:
        """Return the row keys (EmployeeId strings) in current display order.

        Useful for tests and any future T25/T31 wiring that needs to map a
        cursor row back to the underlying employee.
        """
        return [str(row.key.value) for row in self.ordered_rows]

    def filter_by_department(self, dept_id: DepartmentId | None) -> None:
        """Filter rows to a single department; ``None`` clears the filter.

        Given: a dept_id (or ``None`` to reset)
        When: called
        Then: the table shows only employees in that dept (or all employees
              if ``dept_id is None``). Row count changes accordingly.
        """
        self._filter_dept_id = dept_id
        self._populate_rows()

    def sort_by_skill(self) -> None:
        """Sort rows by 스킬 desc. Re-applies the current dept filter.

        Given: the table has rows
        When: called
        Then: rows are sorted by ``employee.skill`` descending.
        """
        self._sort_and_populate(key=lambda e: e.skill)

    def sort_by_satisfaction(self) -> None:
        """Sort rows by 만족도 desc (htop ``M`` mapping).

        Given: the table has rows
        When: called
        Then: rows are sorted by ``employee.satisfaction`` descending.
        """
        self._sort_and_populate(key=lambda e: e.satisfaction)

    def sort_by_salary(self) -> None:
        """Sort rows by 급여 desc (htop ``P`` mapping).

        Given: the table has rows
        When: called
        Then: rows are sorted by ``employee.salary_per_week`` descending.
        """
        self._sort_and_populate(key=lambda e: e.salary_per_week)

    # -------------------------------------------------------------- internals

    def _visible_employees(self) -> list[Employee]:
        """Apply the current dept filter; return the visible employee list."""
        if self._filter_dept_id is None:
            return list(self._all_employees)
        return [e for e in self._all_employees if e.dept_id == self._filter_dept_id]

    def _populate_rows(self) -> None:
        """Clear and rebuild rows in the locked default order (skill-desc).

        Called by the constructor and by ``filter_by_department``. For the
        explicit sort methods, ``_sort_and_populate`` is used instead so we
        don't double-apply the default key.
        """
        self.clear()
        for emp in self._visible_employees():
            self._add_employee_row(emp)
        # Re-apply the default skill-desc sort on top of the filter so that
        # the locked invariant ("default sort: by 스킬 desc") holds even
        # after filter changes.
        self.sort_by_skill()

    def _sort_and_populate(self, *, key: Callable[[Employee], int]) -> None:
        """Sort the visible employees by ``key`` desc and re-add rows.

        ``key`` is a callable taking an Employee and returning the sort
        value. We avoid storing the callable as a public attribute (to keep
        the type surface small); each sort method builds its own closure.
        """
        visible = sorted(
            self._visible_employees(),
            key=key,
            reverse=True,
        )
        self.clear()
        for emp in visible:
            self._add_employee_row(emp)

    def _add_employee_row(self, emp: Employee) -> None:
        """Add one row for ``emp`` using the locked column order."""
        self.add_row(
            str(emp.id),
            emp.name,
            self._dept_label(emp.dept_id),
            str(emp.skill),
            str(emp.tier),
            str(emp.salary_per_week),
            str(emp.satisfaction),
            key=str(emp.id),
        )

    def _dept_label(self, dept_id: DepartmentId) -> str:
        """Return the display label for a dept, or the raw id if unknown."""
        dept = self._departments.get(dept_id)
        if dept is None:
            return str(dept_id)
        return str(dept.type.value)
