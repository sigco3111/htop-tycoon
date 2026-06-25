"""T31: textual ``Pilot`` integration tests (startup, F-keys, save/load).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 672-686:

- **Startup render** — ``HtopTycoonApp`` mounts the 6 locked widget types /
  8 total instances: 1 ``GameHeader`` + 3 ``MetricBar`` (cpu/mem/swap) +
  1 ``OrgTree`` + 1 ``EmployeeTable`` + 1 ``Alert`` + 1 ``HtopFooter``.
- **F-key dispatch** — pressing ``down`` + ``enter`` selects the first
  employee; pressing ``f9`` fires them (count decreases); pressing
  ``f7`` promotes another (tier+1, salary * 1.25).
- **Save→Load round-trip** — running 20 ticks + pressing F2 / clicking
  저장 produces a save file; restarting the app with that load path
  restores tick count and employee IDs.

Per the locked plan MUST-NOT-DO:

- Do NOT use real terminal capture (slow, fragile) — use Pilot's snapshot.
- Do NOT claim "5 widgets" — there are 6 types / 8 instances.

Test ordering mirrors the plan's 3 scenarios (one test per scenario, all
async, all deterministic via ``seed=42``).

The engine's ``new_game(seed)`` returns a state with EMPTY departments and
employees; the F-key scenarios therefore pre-populate ``app.state`` with a
single Engineering department and 5 employees BEFORE mounting the app, so
the widgets have something to render. The engine is unchanged — bootstrap
is a separate concern, out of scope for T31.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.state import (
    DepartmentId,
    EmployeeId,
    GameState,
    new_game,
)
from htop_tycoon.engine.tick import TickEngine
from htop_tycoon.persistence.deserialize import load as persistence_load
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.screens.setup import SetupScreen

# Evidence directory; tests save snapshot text files for the QA scenarios.
EVIDENCE_DIR = Path(".omo/evidence")


# -- Helpers ---------------------------------------------------------------


def _build_eng_dept_with_employees() -> tuple[GameState, dict[EmployeeId, Employee]]:
    """Return ``(state, employees)`` with 1 Engineering dept + 5 employees.

    The dept + employees are constructed directly (no engine hire) so the
    test is fully deterministic and independent of any bootstrap code.
    Five employees is enough for the F9 (count decreases) and F7 (promote)
    assertions and matches the T19 fixture's shape.
    """
    base = new_game(42)
    dept_id = DepartmentId("dept-eng")
    emp_ids = [EmployeeId(f"emp-{i}") for i in range(1, 6)]
    employees = {
        emp_ids[0]: Employee(
            id=emp_ids[0],
            name="Alice",
            dept_id=dept_id,
            skill=9,
            tier=1,
            salary_per_week=2000,
            satisfaction=80,
            hired_tick=0,
        ),
        emp_ids[1]: Employee(
            id=emp_ids[1],
            name="Bob",
            dept_id=dept_id,
            skill=8,
            tier=1,
            salary_per_week=1500,
            satisfaction=60,
            hired_tick=0,
        ),
        emp_ids[2]: Employee(
            id=emp_ids[2],
            name="Carol",
            dept_id=dept_id,
            skill=7,
            tier=1,
            salary_per_week=1800,
            satisfaction=90,
            hired_tick=0,
        ),
        emp_ids[3]: Employee(
            id=emp_ids[3],
            name="Dave",
            dept_id=dept_id,
            skill=6,
            tier=1,
            salary_per_week=1200,
            satisfaction=70,
            hired_tick=0,
        ),
        emp_ids[4]: Employee(
            id=emp_ids[4],
            name="Eve",
            dept_id=dept_id,
            skill=5,
            tier=1,
            salary_per_week=1000,
            satisfaction=50,
            hired_tick=0,
        ),
    }
    department = Department(
        id=dept_id,
        type=DepartmentType.Engineering,
        head_employee_id=emp_ids[0],
        employee_ids=emp_ids,
        founded_tick=0,
        unlocked=True,
    )
    state = dataclasses.replace(
        base,
        departments={dept_id: department},
        employees=employees,
    )
    return state, employees


def _populate_app_state(app: HtopTycoonApp) -> None:
    """Pre-populate ``app.state`` and ``app.engine`` for the F-key scenarios.

    Mutates the App BEFORE mounting, so ``compose()`` sees the populated
    state when it constructs ``OrgTree``, ``EmployeeTable``, and the
    header. The engine is also re-keyed so any subsequent ``_tick_once``
    stays deterministic.
    """
    state, _employees = _build_eng_dept_with_employees()
    app.state = state
    app.engine = TickEngine(state.rng_seed)


# -- Fixtures ---------------------------------------------------------------


@pytest.fixture
def evidence_dir() -> Iterator[Path]:
    """Ensure the evidence directory exists; yield the Path."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    yield EVIDENCE_DIR


# -- Scenario 1: Startup render --------------------------------------------


class TestStartupRender:
    """Given: HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
    When:  mounted via Pilot
    Then:  the 6 locked widget types (8 total instances) are queryable.
    """

    async def test_six_widget_types_eight_instances_mounted(self) -> None:
        """Assert the locked widget count: 6 types, 8 instances.

        Per plan line 676:
            1 header + 3 MetricBar (cpu/mem/swap) + 1 OrgTree +
            1 EmployeeTable + 1 Alert + 1 footer.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()

            # 1 header — exactly one GameHeader
            from htop_tycoon.ui.widgets.header import GameHeader

            headers = app.query(GameHeader)
            assert len(headers) == 1, (
                f"Expected 1 GameHeader, got {len(headers)}"
            )

            # 3 MetricBar instances (cpu/mem/swap)
            from htop_tycoon.ui.widgets.metric_bar import MetricBar

            metric_bars = app.query(MetricBar)
            assert len(metric_bars) == 3, (
                f"Expected 3 MetricBar instances, got {len(metric_bars)}"
            )

            # 1 OrgTree
            from htop_tycoon.ui.widgets.org_tree import OrgTree

            org_trees = app.query(OrgTree)
            assert len(org_trees) == 1, (
                f"Expected 1 OrgTree, got {len(org_trees)}"
            )

            # 1 EmployeeTable
            from htop_tycoon.ui.widgets.employee_table import EmployeeTable

            tables = app.query(EmployeeTable)
            assert len(tables) == 1, (
                f"Expected 1 EmployeeTable, got {len(tables)}"
            )

            # 1 Alert panel
            from htop_tycoon.ui.widgets.alert import Alert

            alerts = app.query(Alert)
            assert len(alerts) == 1, f"Expected 1 Alert, got {len(alerts)}"

            # 1 HtopFooter
            from htop_tycoon.ui.widgets.footer import HtopFooter

            footers = app.query(HtopFooter)
            assert len(footers) == 1, (
                f"Expected 1 HtopFooter, got {len(footers)}"
            )

            # Total: 1 + 3 + 1 + 1 + 1 + 1 = 8 instances across 6 types.
            total = (
                len(headers)
                + len(metric_bars)
                + len(org_trees)
                + len(tables)
                + len(alerts)
                + len(footers)
            )
            assert total == 8, (
                f"Expected 8 total widget instances across 6 types, got {total}"
            )

    async def test_korean_labels_present_in_snapshot(self, evidence_dir: Path) -> None:
        """The startup render shows Korean labels in header + footer + bars.

        Header Korean segments: ``년``, ``분기``, ``주차`` (time format).
        Footer F-row Korean segments: ``도움말``, ``해고`` (etc.).
        MetricBar Korean suffixes: ``매출``, ``재고``, ``부채``.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Trigger a tick so the header / metric bars populate.
            app._tick_once()
            await pilot.pause()

            snapshot = app.export_screenshot()  # type: ignore[attr-defined]

            # Korean segments must appear somewhere in the rendered snapshot.
            # The header includes 시간/부서/제품, footer includes F-row labels,
            # MetricBar includes the locked suffixes.
            korean_markers = [
                "도움말",  # F1 in footer
                "해고",  # F9 in footer
                "매출",  # CPU bar label
                "재고",  # MEM bar label
                "부채",  # SWAP bar label
                "년",  # year suffix in header
            ]
            missing = [m for m in korean_markers if m not in snapshot]
            assert missing == [], (
                f"Korean labels missing from startup snapshot: {missing!r}\n"
                f"Snapshot:\n{snapshot}"
            )

            # Save the snapshot for the QA evidence.
            evidence_file = evidence_dir / "task-31-startup.txt"
            evidence_file.write_text(
                f"# T31 Scenario 1 — Startup render (seed=42)\n\n"
                f"{snapshot}\n",
                encoding="utf-8",
            )
            assert evidence_file.exists()


# -- Scenario 2: F-key dispatch --------------------------------------------


class TestFKeyDispatch:
    """Pressing down + enter selects; f9 fires; f7 promotes."""

    async def test_f9_fires_selected_employee_decreases_count(
        self, evidence_dir: Path
    ) -> None:
        """Select first employee via down + enter → F9 → employee count drops."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        _populate_app_state(app)
        async with app.run_test() as pilot:
            await pilot.pause()

            from htop_tycoon.ui.widgets.employee_table import EmployeeTable

            table = app.query_one(EmployeeTable)
            initial_count = len(table.get_rows())
            assert initial_count > 0, "fresh game must have employees"

            # Focus the table so cursor keys route there.
            table.focus()
            await pilot.pause()

            # Cursor + select — same pattern the spec mandates.
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            # The selected employee id must be set (the EmployeeTable's
            # ``on_data_table_row_selected`` handler populates it).
            assert app._selected_employee_id is not None, (  # type: ignore[attr-defined]
                "down + enter did not select an employee; "
                "_selected_employee_id is still None"
            )
            selected_id = app._selected_employee_id  # type: ignore[attr-defined]
            assert selected_id in app.state.employees  # type: ignore[attr-defined]

            # Press F9 — fire.
            await pilot.press("f9")
            await pilot.pause()

            # GameState is authoritative (per AGENTS.md "State boundary").
            # The EmployeeTable's row cache is a read-only view; we assert
            # on the state dict directly.
            after_count = len(app.state.employees)  # type: ignore[attr-defined]
            assert after_count == initial_count - 1, (
                f"F9 did not fire the selected employee: "
                f"initial={initial_count}, after={after_count}"
            )
            assert selected_id not in app.state.employees  # type: ignore[attr-defined]
            # And the selected id is cleared (the fired employee no longer exists).
            assert app._selected_employee_id is None  # type: ignore[attr-defined]

            snapshot = app.export_screenshot()  # type: ignore[attr-defined]
            (evidence_dir / "task-31-fkeys.txt").write_text(
                f"# T31 Scenario 2 — F-key dispatch (seed=42)\n\n"
                f"selected employee before F9: {selected_id}\n"
                f"initial employee count: {initial_count}\n"
                f"after F9: {after_count}\n\n"
                f"{snapshot}\n",
                encoding="utf-8",
            )

    async def test_f7_promotes_employee_tier_plus_one_salary_times_1_25(
        self, evidence_dir: Path
    ) -> None:
        """Select another employee → F7 → tier+1, salary * 1.25."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        _populate_app_state(app)
        async with app.run_test() as pilot:
            await pilot.pause()

            from htop_tycoon.ui.widgets.employee_table import EmployeeTable

            table = app.query_one(EmployeeTable)

            # Capture state before promote.
            row_keys = table.get_rows()
            assert len(row_keys) >= 2, "need >= 2 employees for promote test"

            # Focus the table so cursor keys route there.
            table.focus()
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            selected_id = app._selected_employee_id  # type: ignore[attr-defined]
            assert selected_id is not None, "down + enter did not select"

            emp_before = app.state.employees[selected_id]  # type: ignore[attr-defined]
            tier_before = emp_before.tier
            salary_before = emp_before.salary_per_week

            # Press F7 — promote.
            await pilot.press("f7")
            await pilot.pause()

            emp_after = app.state.employees[selected_id]  # type: ignore[attr-defined]
            assert emp_after.tier == tier_before + 1, (
                f"F7 did not promote: tier before={tier_before}, "
                f"after={emp_after.tier}"
            )
            # Salary must be round(salary_before * 1.25).
            expected_salary = round(salary_before * 1.25)
            assert emp_after.salary_per_week == expected_salary, (
                f"F7 did not apply 1.25x multiplier: "
                f"salary before={salary_before}, after={emp_after.salary_per_week}, "
                f"expected={expected_salary}"
            )


# -- Scenario 3: Save -> Load round-trip ------------------------------------


class TestSaveLoadRoundTrip:
    """20 ticks + F2 save → restart with --load → tick count + employee IDs match."""

    async def test_save_then_load_restores_tick_and_employees(
        self, tmp_path: Path, evidence_dir: Path
    ) -> None:
        """Given: an HtopTycoonApp running for 20 ticks with a saved state.
        When:  a new HtopTycoonApp is loaded from the save file.
        Then:  tick count == 20 and employee IDs match the original set.
        """
        save_path = tmp_path / "save.json"
        app_a = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app_a._save_path = save_path  # type: ignore[attr-defined]
        async with app_a.run_test() as pilot:
            await pilot.pause()

            # Run 20 ticks via the locked wrapper.
            for _ in range(20):
                app_a._tick_once()
            await pilot.pause()
            assert app_a.state.tick == 20, (
                f"Expected tick==20, got {app_a.state.tick}"
            )

            # Open the SetupScreen via F2 and click 저장.
            await pilot.press("f2")
            await pilot.pause()
            assert isinstance(app_a.screen, SetupScreen)
            save_button = app_a.screen.query_one("#save-button", object)  # type: ignore[union-attr]
            save_button.action_press()  # type: ignore[union-attr]
            await pilot.pause()

            assert save_path.exists(), (
                f"Save did not write file at {save_path}"
            )

            # Snapshot original employee ids BEFORE closing app_a.
            original_employee_ids = set(app_a.state.employees.keys())  # type: ignore[attr-defined]
            original_tick = app_a.state.tick
            original_rng_seed = app_a.state.rng_seed

        # Restart with --load=path (in-process, no subprocess — matches the
        # locked plan line 662 "in-process Pilot test (NOT subprocess)").
        loaded_state: GameState = persistence_load(save_path)
        app_b = HtopTycoonApp(
            seed=loaded_state.rng_seed,
            tick_rate=100,
            no_autosave=True,
        )
        # Rebind state + engine — same protocol used by ``__main__._run_app``.
        app_b.state = loaded_state
        from htop_tycoon.engine.tick import TickEngine

        app_b.engine = TickEngine(loaded_state.rng_seed)

        async with app_b.run_test() as pilot:
            await pilot.pause()

            assert app_b.state.tick == original_tick, (
                f"Loaded tick {app_b.state.tick} != original {original_tick}"
            )
            loaded_employee_ids = set(app_b.state.employees.keys())
            assert loaded_employee_ids == original_employee_ids, (
                f"Loaded employee IDs differ: "
                f"missing={original_employee_ids - loaded_employee_ids}, "
                f"added={loaded_employee_ids - original_employee_ids}"
            )
            assert app_b.state.rng_seed == original_rng_seed

            snapshot = app_b.export_screenshot()  # type: ignore[attr-defined]
            payload = {
                "tick": app_b.state.tick,
                "rng_seed": app_b.state.rng_seed,
                "employee_count": len(app_b.state.employees),  # type: ignore[attr-defined]
                "first_employee_ids": sorted(app_b.state.employees.keys())[:5],  # type: ignore[attr-defined]
                "save_path": str(save_path),
                "save_file_envelope": json.loads(
                    save_path.read_text(encoding="utf-8")
                )["version"],
            }
            (evidence_dir / "task-31-saveload.txt").write_text(
                f"# T31 Scenario 3 — Save->Load round-trip (seed=42)\n\n"
                f"metadata: {json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
                f"snapshot:\n{snapshot}\n",
                encoding="utf-8",
            )
