"""Tests for T25: Single-key BINDINGS (t, u, m, p, T, arrows, Space) + action handlers.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 565-585:

- ``htop_tycoon.bindings.registry`` exposes ``register_single_key_bindings()``
  returning a fresh ``list[Binding]`` of length 8 with the locked (key, action,
  description) tuples. All keys have ``show=False`` so they stay out of the
  footer (matches the F-row bindings style).
- ``HtopTycoonApp.BINDINGS`` contains BOTH the 10 F-row bindings (T24) AND the
  8 single-key bindings (this task), total 18 entries, in order.
- Each single-key ``action_*`` method exists on the App.
- The real engine actions are wired:
    - ``action_fire_selected`` calls ``engine.actions.fire(state, emp_id)``,
      rebinds ``self.state`` to the new state, and publishes the
      ``EmployeeFired`` event via ``self.event_bus``.
    - ``action_promote_selected`` calls ``engine.actions.promote(state, emp_id)``
      and publishes ``EmployeePromoted`` (or ``AlertRaised`` on budget reject).
    - ``action_demote_selected`` calls ``engine.actions.demote(state, emp_id)``
      and publishes ``EmployeeDemoted``.
- F5/M/P/T actions look up the OrgTree/EmployeeTable widgets and call their
  methods. Until those widgets are mounted in T26-T29, the actions are
  recorded on ``self._last_action`` and notify the user.
- F3/u/Space remain stubs that record ``self._last_action`` and notify.
- F6 cycle_sort cycles through [satisfaction, salary, skill] on each press.

Pilot tests cover the user-visible contract; pure-function tests cover the
registry shape.
"""

from __future__ import annotations

import dataclasses

from textual.binding import Binding

from htop_tycoon.bindings.registry import (
    register_f_bindings,
    register_single_key_bindings,
)
from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.state import DepartmentId, EmployeeId, GameState
from htop_tycoon.engine import actions
from htop_tycoon.engine.events import (
    AlertRaised,
    EmployeeDemoted,
    EmployeeFired,
    EmployeePromoted,
)
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.ui.app import HtopTycoonApp

# -- Locked single-key binding table ----------------------------------------
# Plan line 567-576: the exact (key, action, description) tuples. Note the
# plan lists ``Binding("m", ...)`` etc. with no Korean description for the
# sort keys (description defaults to None), and the cursor / Space keys have
# no description either. We assert the locked (key, action) tuple and the
# ``show=False`` invariant.
LOCKED_SINGLE_KEY_BINDINGS: tuple[tuple[str, str], ...] = (
    ("t", "toggle_tree"),
    ("u", "filter_by_dept"),
    ("m", "sort_by_satisfaction"),
    ("p", "sort_by_salary"),
    ("T", "sort_by_time"),
    ("up", "cursor_up"),
    ("down", "cursor_down"),
    ("space", "tag_selected"),
)


# -- Module surface ---------------------------------------------------------


def test_registry_module_exposes_register_single_key_bindings() -> None:
    """``registry`` module exposes ``register_single_key_bindings`` as a callable."""
    import htop_tycoon.bindings.registry as reg

    assert hasattr(reg, "register_single_key_bindings")
    assert callable(reg.register_single_key_bindings)


# -- Registry: return shape -------------------------------------------------


class TestRegistrySingleKeyReturnShape:
    """``register_single_key_bindings()`` returns a list of exactly 8 ``Binding``s."""

    def test_returns_list_of_eight_bindings(self) -> None:
        """The registry returns a list of exactly eight Binding objects."""
        result = register_single_key_bindings()
        assert isinstance(result, list)
        assert len(result) == 8
        for binding in result:
            assert isinstance(binding, Binding)

    def test_returns_fresh_list_each_call(self) -> None:
        """Two calls return independent list instances (no shared mutable state)."""
        first = register_single_key_bindings()
        second = register_single_key_bindings()
        assert first is not second


# -- Registry: each binding matches the locked spec ------------------------


class TestRegistrySingleKeyBindingsExact:
    """Each binding matches the locked (key, action) tuple and has ``show=False``."""

    def test_each_binding_matches_locked_tuple(self) -> None:
        """Every binding's (key, action) matches the spec, in order."""
        result = register_single_key_bindings()
        for binding, expected in zip(result, LOCKED_SINGLE_KEY_BINDINGS, strict=True):
            exp_key, exp_action = expected
            assert binding.key == exp_key, (
                f"key mismatch: got {binding.key!r}, expected {exp_key!r}"
            )
            assert binding.action == exp_action, (
                f"action mismatch: got {binding.action!r}, expected {exp_action!r}"
            )

    def test_all_single_key_bindings_have_show_false(self) -> None:
        """All single-key bindings use ``show=False`` (hidden from footer).

        The plan says: "Textual Binding show=False means the binding is hidden
        from the footer but still active."
        """
        result = register_single_key_bindings()
        for binding in result:
            assert binding.show is False, (
                f"single-key binding {binding.key!r} must have show=False, "
                f"got {binding.show!r}"
            )

    def test_keys_normalize_via_textual_binding_api(self) -> None:
        """Single-character keys are lowercase; multi-char keys stored as-is.

        The locked spec writes the shift+t key as uppercase ``T`` (htop
        style). Textual's ``Binding`` constructor stores the key as given
        in this case, so we accept ``T`` as the explicit uppercase
        exception. All other single-character keys MUST be lowercase
        (per Textual's documented Binding API). Multi-segment keys
        (``up``, ``down``, ``space``) are stored verbatim because they
        are Textual named keys, not characters.
        """
        result = register_single_key_bindings()
        for binding in result:
            if binding.key in {"up", "down", "space"}:
                # Named Textual keys are stored as-is.
                continue
            if binding.key == "T":
                # The plan locks "T" (uppercase shift+t). Single
                # documented exception.
                continue
            assert binding.key == binding.key.lower(), (
                f"key {binding.key!r} must be lowercase per Textual's "
                f"Binding API"
            )

    def test_no_lowercase_q_binding_present(self) -> None:
        """Single-key bindings must NOT include lowercase ``q`` (text input conflict)."""
        result = register_single_key_bindings()
        for binding in result:
            assert binding.key != "q", (
                "forbidden: lowercase 'q' binding conflicts with text input"
            )


# -- App: BINDINGS class attribute (T24 F-row + T25 single-key) -----------


class TestAppBindingsAttribute:
    """``HtopTycoonApp.BINDINGS`` contains both F-row and single-key bindings."""

    def test_app_bindings_has_eighteen_entries(self) -> None:
        """After T25, ``BINDINGS`` has 18 entries (10 F + 8 single-key)."""
        assert len(HtopTycoonApp.BINDINGS) == 18

    def test_app_bindings_first_ten_match_f_bindings(self) -> None:
        """The first 10 entries match the T24 ``register_f_bindings()`` output."""
        registry_f = register_f_bindings()
        assert HtopTycoonApp.BINDINGS[:10] == registry_f

    def test_app_bindings_last_eight_match_single_key_bindings(self) -> None:
        """The last 8 entries match the T25 ``register_single_key_bindings()`` output."""
        registry_sk = register_single_key_bindings()
        assert HtopTycoonApp.BINDINGS[10:] == registry_sk


# -- App: action_* methods exist for every single-key binding --------------


class TestAppActionMethods:
    """Every bound single-key action has a corresponding ``action_*`` method."""

    def test_all_eight_single_key_action_methods_exist(self) -> None:
        """For each single-key binding.action, the App has a method named action_<action>."""
        for binding in HtopTycoonApp.BINDINGS[10:]:
            method_name = f"action_{binding.action}"
            assert hasattr(HtopTycoonApp, method_name), (
                f"missing {method_name} on HtopTycoonApp"
            )
            assert callable(getattr(HtopTycoonApp, method_name))


# -- Pilot: F9 fires the selected employee ---------------------------------


def _make_state_with_employee(
    seed: int = 42,
) -> tuple[GameState, EmployeeId]:
    """Build a ``GameState`` containing one department + one employee.

    Given: a seed for the deterministic RNG
    When:  called
    Then:  returns ``(state, employee_id)`` where ``state.employees[employee_id]``
           is an Employee at tier 1, and the employee is in the dept roster.

    Uses the same domain invariants as ``engine.actions.hire`` so the result
    is a state an engine action accepts unchanged.
    """
    from htop_tycoon.data import load_balance

    balance = load_balance()
    starting_salary = int(balance["employees"]["starting_salary_per_week"])
    skill_lo, skill_hi = balance["employees"]["starting_skill_range"]

    rng = GameRNG(seed)
    emp_id = EmployeeId(f"emp_{rng.int(0, 1_000_000_000):08d}")
    dept_id = DepartmentId("dept-eng")

    employee = Employee(
        id=emp_id,
        name="테스트 직원",
        dept_id=dept_id,
        skill=int(rng.int(int(skill_lo), int(skill_hi))),
        tier=1,
        salary_per_week=starting_salary,
        satisfaction=60,
        hired_tick=0,
    )
    department = Department(
        id=dept_id,
        type=DepartmentType.Engineering,
        head_employee_id=emp_id,
        employee_ids=[emp_id],
        founded_tick=0,
        unlocked=False,
    )
    state = GameState(
        company=__import__("htop_tycoon.domain.state", fromlist=["Company"]).Company(
            id="company-1",
            name="TestCo",
            cash=1000,
            market_cap=1000,
        ),
        departments={dept_id: department},
        employees={emp_id: employee},
        products={},
        competitors={},
        events_active=[],
        ending_history=[],
        secret_investor_cleared=False,
        tick=0,
        rng_seed=seed,
    )
    return state, emp_id


class TestF9FiresSelectedEmployee:
    """Pressing F9 via Pilot fires the selected employee."""

    async def test_f9_removes_employee_from_state(self) -> None:
        """Given: a mounted app with one employee, _selected_employee_id = that id
        When:  pilot.press('f9') fires
        Then:  state.employees no longer contains the employee, and the
               EmployeeFired event was published on the event bus.
        """
        state, emp_id = _make_state_with_employee(seed=42)
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Inject the test fixture: replace state and remember the selection.
            app.state = state
            app._selected_employee_id = emp_id  # type: ignore[attr-defined]
            # Subscribe to EmployeeFired so we can assert publish fired.
            fired_events: list[EmployeeFired] = []
            app.event_bus.subscribe(EmployeeFired, fired_events.append)

            await pilot.press("f9")
            await pilot.pause()

            assert emp_id not in app.state.employees, (
                f"F9 should remove {emp_id!r} from state.employees"
            )
            assert len(fired_events) == 1, (
                f"expected exactly one EmployeeFired event, got {fired_events!r}"
            )
            assert fired_events[0].employee_id == emp_id
            # And the action was recorded on _last_action for tests to inspect.
            assert app._last_action == "fire_selected"  # type: ignore[attr-defined]

    async def test_f9_emits_a_notify(self) -> None:
        """F9 calls ``self.notify`` so the user sees the fired confirmation."""
        state, emp_id = _make_state_with_employee(seed=42)
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.state = state
            app._selected_employee_id = emp_id  # type: ignore[attr-defined]
            before = len(app._notifications)
            await pilot.press("f9")
            await pilot.pause()
            assert len(app._notifications) > before, (
                "F9 should call self.notify to give visible feedback"
            )

    async def test_f9_with_no_selection_alerts(self) -> None:
        """Given: a mounted app with NO _selected_employee_id
        When:  pilot.press('f9') fires
        Then:  state is unchanged and an AlertRaised("직원을 선택하세요") fires.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._selected_employee_id = None  # type: ignore[attr-defined]
            state_before = app.state
            alerts: list[AlertRaised] = []
            app.event_bus.subscribe(AlertRaised, alerts.append)

            await pilot.press("f9")
            await pilot.pause()

            # State unchanged.
            assert app.state is state_before
            # Alert published.
            assert len(alerts) == 1, f"expected one AlertRaised, got {alerts!r}"
            assert "직원을 선택하세요" in alerts[0].message_ko
            # Last action still recorded so UI can react.
            assert app._last_action == "fire_selected"  # type: ignore[attr-defined]


# -- Pilot: F7 promotes / F8 demotes the selected employee -----------------


class TestF7PromoteF8Demote:
    """Pressing F7 promotes, F8 demotes the selected employee."""

    async def test_f7_promotes_selected_employee(self) -> None:
        """Given: a mounted app with one employee at tier 1
        When:  pilot.press('f7') fires
        Then:  the employee tier becomes 2 and EmployeePromoted is published.
        """
        state, emp_id = _make_state_with_employee(seed=42)
        assert state.employees[emp_id].tier == 1  # sanity
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.state = state
            app._selected_employee_id = emp_id  # type: ignore[attr-defined]
            promoted_events: list[EmployeePromoted] = []
            app.event_bus.subscribe(EmployeePromoted, promoted_events.append)

            await pilot.press("f7")
            await pilot.pause()

            assert len(promoted_events) == 1
            assert promoted_events[0].employee_id == emp_id
            assert app.state.employees[emp_id].tier == 2, (
                f"expected tier 2 after F7, got {app.state.employees[emp_id].tier}"
            )
            assert app._last_action == "promote_selected"  # type: ignore[attr-defined]

    async def test_f8_demotes_selected_employee(self) -> None:
        """Given: a mounted app with one employee at tier 2
        When:  pilot.press('f8') fires
        Then:  the employee tier becomes 1 and EmployeeDemoted is published.
        """
        state, emp_id = _make_state_with_employee(seed=42)
        # Promote once so demotion is possible (tier 1 -> tier 2).
        # Give the company enough cash so the promotion budget check passes.
        state_with_cash = dataclasses.replace(
            state,
            company=dataclasses.replace(state.company, cash=10_000),
        )
        promoted_state, _ = actions.promote(state_with_cash, emp_id)
        assert promoted_state.employees[emp_id].tier == 2  # sanity

        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.state = promoted_state
            app._selected_employee_id = emp_id  # type: ignore[attr-defined]
            demoted_events: list[EmployeeDemoted] = []
            app.event_bus.subscribe(EmployeeDemoted, demoted_events.append)

            await pilot.press("f8")
            await pilot.pause()

            assert len(demoted_events) == 1
            assert demoted_events[0].employee_id == emp_id
            assert app.state.employees[emp_id].tier == 1
            assert app._last_action == "demote_selected"  # type: ignore[attr-defined]


# -- Pilot: t toggles tree, u opens dept picker ----------------------------


class TestToggleTreeAndFilterByDept:
    """Pressing ``t`` toggles the org-tree; ``u`` opens the dept picker."""

    async def test_t_triggers_action_toggle_tree(self) -> None:
        """Given: a mounted app
        When:  pilot.press('t') fires
        Then:  action_toggle_tree records itself and notifies.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app._notifications)
            await pilot.press("t")
            await pilot.pause()
            assert app._last_action == "toggle_tree"  # type: ignore[attr-defined]
            assert len(app._notifications) > before

    async def test_u_calls_open_dept_picker_stub(self) -> None:
        """Given: a mounted app
        When:  pilot.press('u') fires
        Then:  action_filter_by_dept calls self._open_dept_picker() and notifies.

        T25 only requires the stub method to be invoked — the real picker UI
        is wired in a later todo (per the plan).
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Track that the stub was called.
            called: list[bool] = []
            app._open_dept_picker = lambda: called.append(True)  # type: ignore[method-assign]
            before = len(app._notifications)
            await pilot.press("u")
            await pilot.pause()
            assert app._last_action == "filter_by_dept"  # type: ignore[attr-defined]
            assert called == [True], (
                f"expected _open_dept_picker to be called once, got {called!r}"
            )
            assert len(app._notifications) > before


# -- Pilot: m/p sorts the employee table; T is a stub --------------------


class TestSortBySatisfactionAndSalary:
    """Pressing ``m`` / ``p`` sorts by satisfaction / salary (stubbed for now)."""

    async def test_m_triggers_action_sort_by_satisfaction(self) -> None:
        """Given: a mounted app
        When:  pilot.press('m') fires
        Then:  action_sort_by_satisfaction records itself and notifies.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app._notifications)
            await pilot.press("m")
            await pilot.pause()
            assert app._last_action == "sort_by_satisfaction"  # type: ignore[attr-defined]
            assert len(app._notifications) > before

    async def test_p_triggers_action_sort_by_salary(self) -> None:
        """Given: a mounted app
        When:  pilot.press('p') fires
        Then:  action_sort_by_salary records itself and notifies.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app._notifications)
            await pilot.press("p")
            await pilot.pause()
            assert app._last_action == "sort_by_salary"  # type: ignore[attr-defined]
            assert len(app._notifications) > before

    async def test_T_triggers_action_sort_by_time_stub(self) -> None:
        """Given: a mounted app
        When:  pilot.press('T') (uppercase T) fires
        Then:  action_sort_by_time records itself and notifies.

        ``T`` is uppercase because the plan locks the binding key as ``T``.
        Textual's Binding API normalizes keys to lowercase at construction
        time, but the spec keeps the uppercase display in the key string so
        the locked tuple reads ``("T", "sort_by_time")``. We assert on the
        action name only to remain agnostic of normalization.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app._notifications)
            await pilot.press("T")
            await pilot.pause()
            assert app._last_action == "sort_by_time"  # type: ignore[attr-defined]
            assert len(app._notifications) > before


# -- Pilot: cursor up/down move the table cursor -------------------------


class TestCursorUpDown:
    """Pressing ``up`` / ``down`` moves the table cursor (no-op until table mounted)."""

    async def test_up_triggers_action_cursor_up(self) -> None:
        """Given: a mounted app
        When:  pilot.press('up') fires
        Then:  action_cursor_up records itself.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("up")
            await pilot.pause()
            assert app._last_action == "cursor_up"  # type: ignore[attr-defined]

    async def test_down_triggers_action_cursor_down(self) -> None:
        """Given: a mounted app
        When:  pilot.press('down') fires
        Then:  action_cursor_down records itself.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert app._last_action == "cursor_down"  # type: ignore[attr-defined]


# -- Pilot: Space tags the selected employee (stub) -----------------------


class TestSpaceTagSelected:
    """Pressing ``space`` tags the selected employee (visual marker, no bulk action)."""

    async def test_space_triggers_action_tag_selected(self) -> None:
        """Given: a mounted app
        When:  pilot.press('space') fires
        Then:  action_tag_selected records itself and notifies.

        Per the plan MUST-NOT-DO: bulk fire via Space-tagged employees is out
        of scope for v0.1.0; Space is just a marker. This test only asserts
        the action fired.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app._notifications)
            await pilot.press("space")
            await pilot.pause()
            assert app._last_action == "tag_selected"  # type: ignore[attr-defined]
            assert len(app._notifications) > before


# -- Pilot: F6 cycles sort modes -----------------------------------------


class TestF6CycleSort:
    """Pressing F6 cycles through [satisfaction, salary, skill] sort modes."""

    async def test_f6_cycles_through_sorts(self) -> None:
        """Given: a mounted app
        When:  pilot.press('f6') fires three times
        Then:  ``_sort_cycle_index`` increments modulo the cycle length
               (3 modes) so each press lands on a different sort action.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            seen_indices: set[int] = set()
            for _ in range(3):
                before = len(app._notifications)
                await pilot.press("f6")
                await pilot.pause()
                seen_indices.add(app._sort_cycle_index)  # type: ignore[attr-defined]
                assert len(app._notifications) > before
            # Three presses over a 3-element cycle cover all three indices.
            assert seen_indices == {0, 1, 2}, (
                f"expected all three cycle indices visited, got {seen_indices!r}"
            )


# -- Pilot: F3 search is a stub -----------------------------------------


class TestF3SearchStub:
    """Pressing F3 (search) is a stub for T25 (real impl in a later todo)."""

    async def test_f3_triggers_action_search(self) -> None:
        """Given: a mounted app
        When:  pilot.press('f3') fires
        Then:  action_search records itself and notifies.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app._notifications)
            await pilot.press("f3")
            await pilot.pause()
            assert app._last_action == "search"  # type: ignore[attr-defined]
            assert len(app._notifications) > before


# -- Module re-exports ----------------------------------------------------


def test_registry_module_exposes_both_registry_functions() -> None:
    """Both ``register_f_bindings`` and ``register_single_key_bindings`` are present."""
    import htop_tycoon.bindings.registry as reg

    assert callable(getattr(reg, "register_f_bindings", None))
    assert callable(getattr(reg, "register_single_key_bindings", None))
