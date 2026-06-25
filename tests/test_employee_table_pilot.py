"""Tests for T19: EmployeeTable + DepartmentDetail panels.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 482-491:

- ``EmployeeTable`` subclasses ``textual.widgets.DataTable`` and shows all
  employees (or filtered by dept) with columns ID, 이름, 부서, 스킬, Tier,
  급여, 만족도.
- Default sort: by 스킬 desc.
- ``M`` key sorts by 만족도 (htop ``M`` mapping) -- exposed via
  ``sort_by_satisfaction()``.
- ``P`` key sorts by salary -- exposed via ``sort_by_salary()``.
- ``u`` keypress shows a dept picker overlay (T25 will wire it; for T19,
  the contract is exposed via ``filter_by_department(dept_id)``).
- ``DepartmentDetail`` subclasses ``textual.widgets.Static`` and shows the
  selected dept's aggregated metrics (total employees, avg skill, weekly
  cost). Updated via ``update_for_department(dept, employees)``.

Read-only display; F7/F8/F9 actions fire from bindings (T25).

Textual widgets require an active App context to construct (the DataTable
calls ``self.app.console`` during ``add_columns``), so EVERY test mounts
the widget inside a tiny ``App`` via Pilot. This matches the spec's
"Pilot test" acceptance criterion and is the only way to drive Textual
widgets headlessly in CI.
"""

from __future__ import annotations

from textual.app import App

from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.state import DepartmentId, EmployeeId
from htop_tycoon.ui.widgets.department_detail import DepartmentDetail
from htop_tycoon.ui.widgets.employee_table import EmployeeTable

# -- Fixtures --------------------------------------------------------------


def _make_dept(
    dept_id: str,
    *,
    dept_type: DepartmentType = DepartmentType.Engineering,
    employee_ids: list[str] | None = None,
) -> Department:
    """Build a Department with sane defaults."""
    return Department(
        id=DepartmentId(dept_id),
        type=dept_type,
        head_employee_id=None,
        employee_ids=[EmployeeId(eid) for eid in (employee_ids or [])],
        founded_tick=0,
        unlocked=False,
    )


def _make_employee(
    emp_id: str,
    dept_id: str,
    *,
    name: str = "Test User",
    skill: int = 5,
    tier: int = 1,
    salary: int = 1000,
    satisfaction: int = 60,
) -> Employee:
    """Build a valid Employee with sane defaults."""
    return Employee(
        id=EmployeeId(emp_id),
        name=name,
        dept_id=DepartmentId(dept_id),
        skill=skill,
        tier=tier,
        salary_per_week=salary,
        satisfaction=satisfaction,
        hired_tick=0,
    )


def _fixture_eng_5() -> tuple[list[Employee], dict[DepartmentId, Department]]:
    """Five Engineering employees with varied skill/satisfaction/salary.

    Skills (desc): 9, 8, 7, 6, 5  -> default sort puts emp-1 first.
    Satisfaction: 80, 60, 90, 70, 50  -> sort_by_satisfaction puts emp-3 first.
    Salary:      2000, 1500, 1800, 1200, 1000  -> sort_by_salary puts emp-1 first.
    """
    dept = _make_dept(
        "dept-eng",
        dept_type=DepartmentType.Engineering,
        employee_ids=["emp-1", "emp-2", "emp-3", "emp-4", "emp-5"],
    )
    employees = [
        _make_employee("emp-1", "dept-eng", name="Alice", skill=9, salary=2000, satisfaction=80),
        _make_employee("emp-2", "dept-eng", name="Bob", skill=8, salary=1500, satisfaction=60),
        _make_employee("emp-3", "dept-eng", name="Carol", skill=7, salary=1800, satisfaction=90),
        _make_employee("emp-4", "dept-eng", name="Dave", skill=6, salary=1200, satisfaction=70),
        _make_employee("emp-5", "dept-eng", name="Eve", skill=5, salary=1000, satisfaction=50),
    ]
    return employees, {dept.id: dept}


class _TableApp(App[None]):
    """Minimal App that mounts an EmployeeTable with the given inputs."""

    def __init__(
        self,
        *,
        employees: list[Employee],
        departments: dict[DepartmentId, Department],
    ) -> None:
        super().__init__()
        self._employees = employees
        self._departments = departments

    def compose(self) -> object:
        yield EmployeeTable(employees=self._employees, departments=self._departments)


class _DetailApp(App[None]):
    """Minimal App that mounts a DepartmentDetail."""

    def compose(self) -> object:
        yield DepartmentDetail()


# -- EmployeeTable: rendering ----------------------------------------------


class TestEmployeeTableRender:
    """EmployeeTable renders all employees by default with the locked columns."""

    async def test_default_sort_is_by_skill_desc(self) -> None:
        """Given: 5 Engineering employees with skills 9..5
        When: EmployeeTable is mounted via Pilot
        Then: rows are in skill-desc order: emp-1 (skill=9) first.
        """
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            rows = table.get_rows()
            assert rows[0] == "emp-1"

    async def test_columns_match_locked_contract(self) -> None:
        """The columns are exactly: ID, 이름, 부서, 스킬, Tier, 급여, 만족도.

        Locks the T19 spec: 7 columns in this order with these Korean labels.
        """
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            labels = [str(col.label) for col in table.ordered_columns]
            assert labels == ["ID", "이름", "부서", "스킬", "Tier", "급여", "만족도"]

    async def test_row_count_matches_employee_count(self) -> None:
        """Given: 5 employees
        When: EmployeeTable is mounted
        Then: row_count == 5
        """
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            assert table.row_count == 5


# -- EmployeeTable: sort_by_satisfaction / sort_by_salary ------------------


class TestEmployeeTableSort:
    """sort_by_skill (default), sort_by_satisfaction, sort_by_salary."""

    async def test_sort_by_satisfaction_desc(self) -> None:
        """Given: 5 employees with satisfactions 80,60,90,70,50
        When: sort_by_satisfaction() is called
        Then: rows are in satisfaction-desc order: emp-3 (90) first.
        """
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            table.sort_by_satisfaction()
            await pilot.pause()
            rows = table.get_rows()
            assert rows[0] == "emp-3"
            # Verify full desc ordering
            id_to_sat = {e.id: e.satisfaction for e in employees}
            satisfactions = [id_to_sat[EmployeeId(rid)] for rid in rows]
            assert satisfactions == sorted(satisfactions, reverse=True)

    async def test_sort_by_salary_desc(self) -> None:
        """Given: 5 employees with salaries 2000,1500,1800,1200,1000
        When: sort_by_salary() is called
        Then: rows are in salary-desc order: emp-1 (2000) first.
        """
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            table.sort_by_salary()
            await pilot.pause()
            rows = table.get_rows()
            assert rows[0] == "emp-1"
            id_to_sal = {e.id: e.salary_per_week for e in employees}
            salaries = [id_to_sal[EmployeeId(rid)] for rid in rows]
            assert salaries == sorted(salaries, reverse=True)


# -- EmployeeTable: filter_by_department -----------------------------------


class TestEmployeeTableFilter:
    """filter_by_department filters rows to one dept (or shows all when None)."""

    async def test_filter_by_department_keeps_only_matching(self) -> None:
        """Given: 5 Engineering employees
        When: filter_by_department(DepartmentId('dept-eng')) is called
        Then: row_count stays 5 (all are Engineering).

        Acceptance criteria from the plan: 'selecting Engineering filters to 5 rows'.
        """
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            table.filter_by_department(DepartmentId("dept-eng"))
            await pilot.pause()
            assert table.row_count == 5
            assert set(table.get_rows()) == {"emp-1", "emp-2", "emp-3", "emp-4", "emp-5"}

    async def test_filter_by_different_dept_filters_out(self) -> None:
        """Given: 5 Engineering employees + a Sales dept
        When: filter_by_department(<sales dept id>) is called
        Then: row_count becomes 0 (no Sales employees in fixture).
        """
        employees, depts = _fixture_eng_5()
        sales_dept = _make_dept("dept-sales", dept_type=DepartmentType.Sales)
        depts[sales_dept.id] = sales_dept
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            table.filter_by_department(DepartmentId("dept-sales"))
            await pilot.pause()
            assert table.row_count == 0

    async def test_filter_with_none_resets_to_all(self) -> None:
        """Given: a table filtered to one dept
        When: filter_by_department(None) is called
        Then: all employees are shown again.
        """
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            table.filter_by_department(DepartmentId("dept-eng"))
            await pilot.pause()
            assert table.row_count == 5
            table.filter_by_department(None)
            await pilot.pause()
            assert table.row_count == 5

    async def test_empty_dept_shows_zero_rows_without_crash(self) -> None:
        """QA failure path from the plan: 'empty dept -> table shows 0 rows, no crash'."""
        dept = _make_dept("dept-empty", dept_type=DepartmentType.Operations)
        employees: list[Employee] = []
        app = _TableApp(employees=employees, departments={dept.id: dept})
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            table.filter_by_department(dept.id)
            await pilot.pause()
            assert table.row_count == 0


# -- DepartmentDetail: aggregation -----------------------------------------


class TestDepartmentDetailUpdate:
    """update_for_department renders the dept's aggregated metrics."""

    async def test_update_for_department_renders_employee_count(self) -> None:
        """Given: a DepartmentDetail + Engineering with 5 employees
        When: update_for_department(dept, employees) is called
        Then: rendered text contains '5' for the employee count.
        """
        employees, depts = _fixture_eng_5()
        app = _DetailApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            detail = app.query_one(DepartmentDetail)
            eng = depts[DepartmentId("dept-eng")]
            detail.update_for_department(eng, employees)
            await pilot.pause()
            text = str(detail.renderable)
            assert "5" in text

    async def test_update_for_department_renders_avg_skill(self) -> None:
        """Skills 9,8,7,6,5 -> avg 7.0 -> rendered text contains '7'."""
        employees, depts = _fixture_eng_5()
        app = _DetailApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            detail = app.query_one(DepartmentDetail)
            eng = depts[DepartmentId("dept-eng")]
            detail.update_for_department(eng, employees)
            await pilot.pause()
            text = str(detail.renderable)
            assert "7" in text

    async def test_update_for_department_renders_weekly_cost(self) -> None:
        """Salaries 2000+1500+1800+1200+1000 = 7500 -> rendered text contains '7500'."""
        employees, depts = _fixture_eng_5()
        app = _DetailApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            detail = app.query_one(DepartmentDetail)
            eng = depts[DepartmentId("dept-eng")]
            detail.update_for_department(eng, employees)
            await pilot.pause()
            text = str(detail.renderable)
            assert "7500" in text

    async def test_update_for_none_department_renders_placeholder(self) -> None:
        """Given: DepartmentDetail with no dept selected
        When: update_for_department(None, []) is called
        Then: rendered text is non-empty and indicates no selection.
        """
        app = _DetailApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            detail = app.query_one(DepartmentDetail)
            detail.update_for_department(None, [])
            await pilot.pause()
            text = str(detail.renderable)
            assert text != ""
            assert len(text) > 0


# -- Pilot scenarios from the plan's acceptance criteria ------------------


class TestEmployeeTablePilotAcceptance:
    """The exact acceptance scenarios from .omo/plans/htop-tycoon.md line 487-490."""

    async def test_acceptance_table_renders_5_rows(self) -> None:
        """Plan acceptance: 'Pilot test confirms table renders 5 rows'."""
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            assert table.row_count == 5

    async def test_acceptance_filter_eng_to_5_rows(self) -> None:
        """Plan acceptance: 'selecting Engineering filters to 5 rows'."""
        employees, depts = _fixture_eng_5()
        # Add another empty dept so 'filter' is meaningful.
        sales_dept = _make_dept("dept-sales", dept_type=DepartmentType.Sales)
        depts[sales_dept.id] = sales_dept
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            # Without filter: 5 rows
            assert table.row_count == 5
            table.filter_by_department(DepartmentId("dept-eng"))
            await pilot.pause()
            assert table.row_count == 5
            # Verify ALL the rows are Engineering employees.
            assert set(table.get_rows()) == {"emp-1", "emp-2", "emp-3", "emp-4", "emp-5"}

    async def test_acceptance_M_sorts_by_satisfaction_desc(self) -> None:
        """Plan acceptance: 'M sorts by satisfaction desc'.

        We drive ``sort_by_satisfaction()`` directly (the method that the
        M-key binding in T25 will call). The displayed ordering must put
        emp-3 (satisfaction=90) at row 0.
        """
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            table.sort_by_satisfaction()
            await pilot.pause()
            assert table.get_rows()[0] == "emp-3"

    async def test_acceptance_happy_5_employees_visible(self) -> None:
        """QA happy scenario: load fixture -> table shows 5 employees."""
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            assert table.row_count == 5
            assert len(table.get_rows()) == 5

    async def test_acceptance_happy_press_M_resorts(self) -> None:
        """QA happy scenario: press M -> re-sorted."""
        employees, depts = _fixture_eng_5()
        app = _TableApp(employees=employees, departments=depts)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            # Default order: emp-1 (skill=9) first.
            assert table.get_rows()[0] == "emp-1"
            table.sort_by_satisfaction()
            await pilot.pause()
            # After M (sort by satisfaction): emp-3 (90) first.
            assert table.get_rows()[0] == "emp-3"

    async def test_acceptance_failure_empty_dept_no_crash(self) -> None:
        """QA failure scenario: empty dept -> table shows 0 rows, no crash."""
        dept = _make_dept("dept-empty", dept_type=DepartmentType.Finance)
        app = _TableApp(employees=[], departments={dept.id: dept})
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(EmployeeTable)
            table.filter_by_department(dept.id)
            await pilot.pause()
            assert table.row_count == 0


# -- DepartmentDetail Pilot render -----------------------------------------


class TestDepartmentDetailPilot:
    """DepartmentDetail renders inside a Pilot app."""

    async def test_pilot_detail_renders_metrics(self) -> None:
        """Given: DepartmentDetail mounted in a tiny app
        When: Pilot pauses + update_for_department is called
        Then: rendered text contains employee count and weekly cost.
        """
        employees, depts = _fixture_eng_5()
        eng = depts[DepartmentId("dept-eng")]
        app = _DetailApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            detail = app.query_one(DepartmentDetail)
            detail.update_for_department(eng, employees)
            await pilot.pause()
            text = str(detail.renderable)
            assert "5" in text
            assert "7500" in text

    async def test_pilot_detail_empty_dept(self) -> None:
        """Updating with no dept renders the empty placeholder."""
        app = _DetailApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            detail = app.query_one(DepartmentDetail)
            detail.update_for_department(None, [])
            await pilot.pause()
            text = str(detail.renderable)
            assert text != ""
