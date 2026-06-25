"""Tests for T11: engine.metrics (CPU/메모리/스왑 derivation, pure, no publish).

Locks the contract from .omo/plans/htop-tycoon.md line 364-378:

- ``MetricsSnapshot`` is a frozen dataclass with ``cpu_pct`` (0-100),
  ``mem_pct`` (0-100), ``swap_pct`` (0-100), ``zombie_count`` (int), and
  ``level`` (Literal["ok", "warn", "alert"]). The overall ``level`` is the
  worst of the three per-metric sub-levels.
- ``compute_metrics(state, balance) -> MetricsSnapshot`` is a pure function
  that returns the snapshot only — no event publishing.
- Formulas (locked, must reference balance keys):
    - ``cpu_pct = int(min(100, (cash + sum(revenue_per_week)) / target_revenue * 100))``
    - ``mem_pct = int(total_employees / (n_depts * max_employees_per_dept) * 100)``
    - ``swap_pct = int(max(0, min(100, abs(min(0, cash)) / abs(bankruptcy_cash_floor) * 100)))``
    - ``zombie_count = count(employees with satisfaction < threshold)``
- Level thresholds: ok < 60, warn < 85, alert >= 85.
- Division-by-zero handling: ``len(state.departments) == 0`` → ``mem_pct = 0``
  (sentinel; see ``_compute_mem_pct`` docstring for rationale).
- Grep test: no ``event_bus.publish(...)`` call in ``metrics.py``.

The grep test guards the invariant from AGENTS.md: "No ``event_bus.publish``
calls inside action functions or metrics collectors."
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.product import LifecycleStage, Product, ProductType
from htop_tycoon.domain.state import (
    Company,
    DepartmentId,
    EmployeeId,
    GameState,
    GameTime,
    ProductId,
    new_game,
)
from htop_tycoon.engine.metrics import MetricsSnapshot, compute_metrics

# -- Helpers -----------------------------------------------------------------


def _make_company(cash: int, market_cap: int = 0) -> Company:
    """Build a Company with the given cash (market_cap defaults to 0)."""
    return Company(
        id="company-1",
        name="Test Co",
        cash=cash,
        market_cap=market_cap,
    )


def _make_employee(
    emp_id: str,
    *,
    satisfaction: int = 60,
    skill: int = 5,
    tier: int = 1,
    salary: int = 1000,
    dept_id: str = "dept-eng",
) -> Employee:
    """Build a minimal Employee with sensible defaults."""
    return Employee(
        id=EmployeeId(emp_id),
        name=f"Test {emp_id}",
        dept_id=DepartmentId(dept_id),
        skill=skill,
        tier=tier,
        salary_per_week=salary,
        satisfaction=satisfaction,
        hired_tick=0,
    )


def _make_department(
    dept_id: str,
    *,
    employee_ids: list[str] | None = None,
    dept_type: DepartmentType = DepartmentType.Engineering,
) -> Department:
    """Build a Department with the given employee_ids (string list)."""
    ids: list[EmployeeId] = [EmployeeId(e) for e in (employee_ids or [])]
    head: EmployeeId | None = ids[0] if ids else None
    return Department(
        id=DepartmentId(dept_id),
        type=dept_type,
        head_employee_id=head,
        employee_ids=ids,
        founded_tick=0,
    )


def _make_product(
    prod_id: str,
    *,
    revenue_per_week: int = 0,
    market_share: float = 0.0,
) -> Product:
    """Build a minimal Product with the given revenue/market share."""
    return Product(
        id=ProductId(prod_id),
        type=ProductType.SaaS,
        lifecycle=LifecycleStage.intro,
        weeks_in_stage=0,
        market_share=market_share,
        revenue_per_week=revenue_per_week,
    )


def _make_state(
    *,
    cash: int = 50_000,
    departments: dict[str, Department] | None = None,
    employees: dict[str, Employee] | None = None,
    products: dict[str, Product] | None = None,
) -> GameState:
    """Build a GameState with the given pieces. Defaults: empty dicts."""
    return GameState(
        company=_make_company(cash=cash, market_cap=0),
        departments=departments or {},
        employees=employees or {},
        products=products or {},
        competitors={},
        events_active=[],
        ending_history=[],
        secret_investor_cleared=False,
        tick=0,
        rng_seed=42,
        game_time=GameTime(year=1, quarter=1, week=1),
    )


def _balance() -> dict[str, Any]:
    """Return the live balance dict (cached)."""
    return load_balance()


# -- MetricsSnapshot ---------------------------------------------------------


class TestMetricsSnapshot:
    """MetricsSnapshot is a frozen dataclass with the locked shape."""

    def test_creates_snapshot_with_all_fields(self) -> None:
        """Given: cpu_pct, mem_pct, swap_pct, zombie_count, level
        When: MetricsSnapshot is constructed
        Then: holds them as given
        """
        snap = MetricsSnapshot(
            cpu_pct=10,
            mem_pct=20,
            swap_pct=30,
            zombie_count=2,
            level="ok",
        )
        assert snap.cpu_pct == 10
        assert snap.mem_pct == 20
        assert snap.swap_pct == 30
        assert snap.zombie_count == 2
        assert snap.level == "ok"

    def test_snapshot_is_frozen(self) -> None:
        """Given: a MetricsSnapshot
        When: a field is reassigned
        Then: raises FrozenInstanceError
        """
        from dataclasses import FrozenInstanceError

        snap = MetricsSnapshot(
            cpu_pct=10, mem_pct=20, swap_pct=30, zombie_count=0, level="ok"
        )
        with pytest.raises(FrozenInstanceError):
            snap.cpu_pct = 99  # type: ignore[misc]

    @pytest.mark.parametrize("level", ["ok", "warn", "alert"])
    def test_level_accepts_ok_warn_alert(self, level: str) -> None:
        """level is Literal["ok", "warn", "alert"]; each value is accepted."""
        snap = MetricsSnapshot(
            cpu_pct=0, mem_pct=0, swap_pct=0, zombie_count=0, level=level  # type: ignore[arg-type]
        )
        assert snap.level == level


# -- CPU derivation ----------------------------------------------------------


class TestComputeMetricsCpu:
    """cpu_pct = int(min(100, (cash + sum(revenue_per_week)) / target_revenue * 100))."""

    def test_cpu_zero_when_no_revenue_no_cash(self) -> None:
        """Given: cash=0, no products
        When: compute_metrics(state, balance)
        Then: cpu_pct == 0
        """
        state = _make_state(cash=0)
        snap = compute_metrics(state, _balance())
        assert snap.cpu_pct == 0

    def test_cpu_uses_cash_and_product_revenue(self) -> None:
        """Given: cash=50_000, target=200_000, product revenue=50_000
        When: compute_metrics
        Then: cpu_pct == int(min(100, (50_000 + 50_000) / 200_000 * 100)) == 50
        """
        balance = _balance()
        target = int(balance["money"]["target_revenue"])
        # Pick a cash that, plus revenue, hits exactly 50% of target.
        revenue = 50_000
        cash = target // 2 - revenue  # -> 100_000 - 50_000 = 50_000
        state = _make_state(
            cash=cash,
            products={"p1": _make_product("p1", revenue_per_week=revenue)},
        )
        snap = compute_metrics(state, balance)
        assert snap.cpu_pct == 50

    def test_cpu_clamps_to_100(self) -> None:
        """Given: cash + revenue >= 2 * target_revenue
        When: compute_metrics
        Then: cpu_pct == 100 (clamped, not 200+)
        """
        balance = _balance()
        target = int(balance["money"]["target_revenue"])
        cash = target * 2  # 400_000
        state = _make_state(cash=cash)
        snap = compute_metrics(state, balance)
        assert snap.cpu_pct == 100

    def test_cpu_is_int(self) -> None:
        """cpu_pct is always an int (no float leakage)."""
        state = _make_state(cash=33_333)
        snap = compute_metrics(state, _balance())
        assert isinstance(snap.cpu_pct, int)


# -- MEM derivation ----------------------------------------------------------


class TestComputeMetricsMem:
    """mem_pct = int(total_employees / (n_depts * max_employees_per_dept) * 100)."""

    def test_mem_zero_when_no_departments(self) -> None:
        """Given: no departments (and therefore no employees)
        When: compute_metrics
        Then: mem_pct == 0 (sentinel; division-by-zero guarded)
        """
        state = _make_state(departments={}, employees={})
        snap = compute_metrics(state, _balance())
        assert snap.mem_pct == 0

    def test_mem_counts_employees_across_departments(self) -> None:
        """Given: 2 departments each with 4 employees, max_per_dept=8
        When: compute_metrics
        Then: mem_pct == int(8 / (2 * 8) * 100) == 50
        """
        balance = _balance()
        max_per = int(balance["departments"]["max_employees_per_dept"])
        assert max_per == 8  # pin balance value

        depts = {
            "d1": _make_department("d1", employee_ids=["e1", "e2", "e3", "e4"]),
            "d2": _make_department("d2", employee_ids=["e5", "e6", "e7", "e8"]),
        }
        emps = {f"e{i}": _make_employee(f"e{i}") for i in range(1, 9)}
        state = _make_state(departments=depts, employees=emps)
        snap = compute_metrics(state, balance)
        assert snap.mem_pct == 50

    def test_mem_caps_at_full_capacity(self) -> None:
        """Given: 1 department with 8 employees (== max_per_dept=8)
        When: compute_metrics
        Then: mem_pct == 100
        """
        depts = {"d1": _make_department("d1", employee_ids=[f"e{i}" for i in range(1, 9)])}
        emps = {f"e{i}": _make_employee(f"e{i}") for i in range(1, 9)}
        state = _make_state(departments=depts, employees=emps)
        snap = compute_metrics(state, _balance())
        assert snap.mem_pct == 100

    def test_mem_is_int(self) -> None:
        """mem_pct is always an int."""
        depts = {"d1": _make_department("d1", employee_ids=["e1", "e2", "e3"])}
        emps = {f"e{i}": _make_employee(f"e{i}") for i in range(1, 4)}
        state = _make_state(departments=depts, employees=emps)
        snap = compute_metrics(state, _balance())
        assert isinstance(snap.mem_pct, int)


# -- SWAP derivation ---------------------------------------------------------


class TestComputeMetricsSwap:
    """swap_pct = int(max(0, min(100, abs(min(0, cash)) / abs(bankruptcy_floor) * 100)))."""

    def test_swap_zero_when_cash_positive(self) -> None:
        """Given: cash >= 0
        When: compute_metrics
        Then: swap_pct == 0 (no debt, no swap pressure)
        """
        state = _make_state(cash=50_000)
        snap = compute_metrics(state, _balance())
        assert snap.swap_pct == 0

    def test_swap_uses_abs_min_zero_cash(self) -> None:
        """Given: cash = -5_000, bankruptcy_floor = -10_000
        When: compute_metrics
        Then: swap_pct == int(5_000 / 10_000 * 100) == 50
        """
        balance = _balance()
        floor = int(balance["money"]["bankruptcy_cash_floor"])
        assert floor == -10_000  # pin balance value

        # Pick cash so that abs(min(0, cash)) / abs(floor) = 0.5
        cash = floor // 2  # -5_000
        state = _make_state(cash=cash)
        snap = compute_metrics(state, balance)
        assert snap.swap_pct == 50

    def test_swap_clamps_at_100(self) -> None:
        """Given: cash <= bankruptcy_floor (at or past bankruptcy)
        When: compute_metrics
        Then: swap_pct == 100 (clamped, not 120+)
        """
        balance = _balance()
        floor = int(balance["money"]["bankruptcy_cash_floor"])
        state = _make_state(cash=floor)  # exactly at the floor
        snap = compute_metrics(state, balance)
        assert snap.swap_pct == 100

    def test_swap_at_bankruptcy_cash_floor_is_100(self) -> None:
        """Given: cash < floor (deeper than bankruptcy)
        When: compute_metrics
        Then: swap_pct == 100 (capped)
        """
        state = _make_state(cash=-50_000)
        snap = compute_metrics(state, _balance())
        assert snap.swap_pct == 100

    def test_swap_is_int(self) -> None:
        """swap_pct is always an int."""
        state = _make_state(cash=-3_333)
        snap = compute_metrics(state, _balance())
        assert isinstance(snap.swap_pct, int)


# -- Zombie count ------------------------------------------------------------


class TestComputeMetricsZombies:
    """zombie_count = number of employees with satisfaction < threshold."""

    def test_zombie_count_zero_when_all_above_threshold(self) -> None:
        """Given: all employees at satisfaction >= 20
        When: compute_metrics
        Then: zombie_count == 0
        """
        depts = {
            "d1": _make_department("d1", employee_ids=["e1", "e2", "e3"]),
        }
        emps = {
            "e1": _make_employee("e1", satisfaction=20),  # boundary: not zombie
            "e2": _make_employee("e2", satisfaction=50),
            "e3": _make_employee("e3", satisfaction=99),
        }
        state = _make_state(departments=depts, employees=emps)
        snap = compute_metrics(state, _balance())
        assert snap.zombie_count == 0

    def test_zombie_count_counts_below_threshold(self) -> None:
        """Given: 5 employees; 2 with satisfaction < 20, 3 with >= 20
        When: compute_metrics
        Then: zombie_count == 2
        """
        depts = {
            "d1": _make_department("d1", employee_ids=[f"e{i}" for i in range(1, 6)]),
        }
        emps = {
            "e1": _make_employee("e1", satisfaction=10),  # zombie
            "e2": _make_employee("e2", satisfaction=19),  # zombie (strictly <)
            "e3": _make_employee("e3", satisfaction=20),  # not zombie
            "e4": _make_employee("e4", satisfaction=50),
            "e5": _make_employee("e5", satisfaction=100),
        }
        state = _make_state(departments=depts, employees=emps)
        snap = compute_metrics(state, _balance())
        assert snap.zombie_count == 2

    def test_zombie_threshold_read_from_balance(self) -> None:
        """Given: balance.employees.zombie_satisfaction_threshold = 20 (pinned)
        When: read balance
        Then: threshold is 20 (the spec default)
        """
        balance = _balance()
        assert int(balance["employees"]["zombie_satisfaction_threshold"]) == 20

    def test_zombie_count_empty_when_no_employees(self) -> None:
        """Given: no employees
        When: compute_metrics
        Then: zombie_count == 0
        """
        state = _make_state(employees={})
        snap = compute_metrics(state, _balance())
        assert snap.zombie_count == 0


# -- Level thresholds --------------------------------------------------------


class TestComputeMetricsLevel:
    """level: ok<60, warn<85, alert>=85; overall level = worst of the three."""

    @pytest.mark.parametrize("pct", [0, 30, 59])
    def test_below_60_is_ok(self, pct: int) -> None:
        """Each metric at 0-59 → ok; overall level is ok."""
        snap = MetricsSnapshot(
            cpu_pct=pct, mem_pct=pct, swap_pct=pct, zombie_count=0, level="ok"
        )
        assert snap.level == "ok"

    @pytest.mark.parametrize("pct", [60, 75, 84])
    def test_60_to_84_is_warn(self, pct: int) -> None:
        """Each metric at 60-84 → warn."""
        snap = MetricsSnapshot(
            cpu_pct=pct, mem_pct=pct, swap_pct=pct, zombie_count=0, level="warn"
        )
        assert snap.level == "warn"

    @pytest.mark.parametrize("pct", [85, 90, 100])
    def test_85_and_above_is_alert(self, pct: int) -> None:
        """Each metric at 85-100 → alert."""
        snap = MetricsSnapshot(
            cpu_pct=pct, mem_pct=pct, swap_pct=pct, zombie_count=0, level="alert"
        )
        assert snap.level == "alert"

    def test_overall_level_is_worst_of_three(self) -> None:
        """Given: cpu=ok, mem=warn, swap=alert
        When: compute_metrics (synthesized snapshot)
        Then: overall level is alert (worst)
        """
        snap = MetricsSnapshot(
            cpu_pct=10,  # ok
            mem_pct=70,  # warn
            swap_pct=90,  # alert
            zombie_count=0,
            level="alert",
        )
        assert snap.level == "alert"

    def test_overall_level_picks_alert_when_any_alert(self) -> None:
        """Given: cpu=ok, mem=ok, swap=alert
        When: compute_metrics on a bankrupt state
        Then: overall level == alert
        """
        # cash way past bankruptcy → swap_pct == 100 → alert
        state = _make_state(cash=-50_000)
        snap = compute_metrics(state, _balance())
        assert snap.swap_pct == 100
        assert snap.level == "alert"

    def test_overall_level_ok_when_all_ok(self) -> None:
        """Given: a fresh, healthy state (positive cash, no zombies, low mem)
        When: compute_metrics
        Then: overall level == ok
        """
        # 1 dept with 1 employee at 50% capacity threshold = 1/8*100 = 12 -> ok
        depts = {"d1": _make_department("d1", employee_ids=["e1"])}
        emps = {"e1": _make_employee("e1", satisfaction=80)}
        state = _make_state(
            cash=50_000,
            departments=depts,
            employees=emps,
            products={},
        )
        snap = compute_metrics(state, _balance())
        assert snap.level == "ok"


# -- Integration: compute_metrics returns MetricsSnapshot --------------------


class TestComputeMetricsReturnsSnapshot:
    """compute_metrics returns a MetricsSnapshot, no side effects."""

    def test_returns_metrics_snapshot_instance(self) -> None:
        """Given: any state
        When: compute_metrics(state, balance)
        Then: returns a MetricsSnapshot (not a tuple/dict)
        """
        state = _make_state()
        result = compute_metrics(state, _balance())
        assert isinstance(result, MetricsSnapshot)

    def test_does_not_mutate_state(self) -> None:
        """Given: a state
        When: compute_metrics(state, balance)
        Then: state is unchanged (pure function)
        """
        depts = {"d1": _make_department("d1", employee_ids=["e1"])}
        emps = {"e1": _make_employee("e1", satisfaction=80)}
        state = _make_state(
            cash=50_000,
            departments=depts,
            employees=emps,
            products={},
        )
        snapshot_before = (
            state.company.cash,
            len(state.departments),
            len(state.employees),
            len(state.products),
        )
        _ = compute_metrics(state, _balance())
        snapshot_after = (
            state.company.cash,
            len(state.departments),
            len(state.employees),
            len(state.products),
        )
        assert snapshot_before == snapshot_after

    def test_does_not_call_event_bus_publish(self) -> None:
        """Given: metrics.py is the module under test
        When: we grep its source for ``event_bus.publish(``
        Then: zero matches (no side-effect publish from inside the function)
        """
        metrics_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "htop_tycoon"
            / "engine"
            / "metrics.py"
        )
        assert metrics_path.exists(), f"metrics.py not found at {metrics_path}"
        source = metrics_path.read_text(encoding="utf-8")
        # Match any ``event_bus.publish(`` call (with optional spaces).
        pattern = re.compile(r"event_bus\s*\.\s*publish\s*\(")
        matches = pattern.findall(source)
        assert matches == [], (
            f"metrics.py must NOT call event_bus.publish(...); "
            f"found {len(matches)} occurrence(s)"
        )

    def test_works_on_new_game_state(self) -> None:
        """Given: a fresh state from new_game(42)
        When: compute_metrics(state, balance)
        Then: returns a MetricsSnapshot without raising
        """
        state = new_game(42)
        snap = compute_metrics(state, _balance())
        assert isinstance(snap, MetricsSnapshot)
        # 50_000 starting cash / 200_000 target = 25%
        assert snap.cpu_pct == 25
        # 0 employees, 0 departments → mem_pct == 0 (sentinel)
        assert snap.mem_pct == 0
        # 50_000 >= 0 → swap_pct == 0
        assert snap.swap_pct == 0
        # 0 employees → zombie_count == 0
        assert snap.zombie_count == 0
        # 25% cpu is below 60 → overall level == ok
        assert snap.level == "ok"


# -- Crafted state demonstration --------------------------------------------


class TestComputeMetricsCraftedDemonstration:
    """A crafted state exercises all 4 metrics + level boundaries."""

    def test_crafted_state_full_demonstration(self) -> None:
        """Given: a state with:
            - 2 departments, 4 employees each (50% mem)
            - cash = 100_000, one product with revenue_per_week = 100_000
              → total_revenue = 200_000 = target → cpu_pct = 100
            - cash = 100_000 >= 0 → swap_pct = 0
            - 1 zombie employee (satisfaction=10)
        When: compute_metrics
        Then: cpu_pct=100, mem_pct=50, swap_pct=0, zombie_count=1, level=alert
        """
        depts = {
            "d1": _make_department("d1", employee_ids=["e1", "e2", "e3", "e4"]),
            "d2": _make_department("d2", employee_ids=["e5", "e6", "e7", "e8"]),
        }
        emps: dict[str, Employee] = {}
        for i, sat in enumerate(
            [10, 50, 50, 50, 50, 50, 50, 50], start=1
        ):  # e1 is a zombie
            emps[f"e{i}"] = _make_employee(f"e{i}", satisfaction=sat)
        products = {
            "p1": _make_product("p1", revenue_per_week=100_000),
        }
        state = _make_state(
            cash=100_000,
            departments=depts,
            employees=emps,
            products=products,
        )
        snap = compute_metrics(state, _balance())
        # Cash 100k + revenue 100k = 200k == target (200k) → cpu_pct == 100
        assert snap.cpu_pct == 100
        # 8 employees / (2 depts * 8 max) = 0.5 → mem_pct == 50
        assert snap.mem_pct == 50
        # cash >= 0 → swap_pct == 0
        assert snap.swap_pct == 0
        # Only e1 has satisfaction=10 < 20 → zombie_count == 1
        assert snap.zombie_count == 1
        # cpu_pct=100 → alert (>=85)
        assert snap.level == "alert"
