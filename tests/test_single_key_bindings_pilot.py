"""Tests for T25: Single-key BINDINGS (t, u, m, s, i, arrows, Space) + action handlers.

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
    ("s", "sort_by_salary"),
    ("i", "sort_by_time"),
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
        All single-character keys MUST be lowercase (per the Wave-7
        lowercase-only convention and Textual's documented Binding API).
        Multi-segment keys (``up``, ``down``, ``space``) are stored
        verbatim because they are Textual named keys, not characters.
        """
        result = register_single_key_bindings()
        for binding in result:
            if binding.key in {"up", "down", "space"}:
                # Named Textual keys are stored as-is.
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

    def test_app_bindings_has_twenty_entries(self) -> None:
        """``BINDINGS`` has 20 entries (10 F + 8 single-key + 2 extras).

        Wave 7 added one extra single-key entry (uppercase ``P`` →
        toggle_pause) registered via ``register_extra_bindings()``;
        Wave 8 added a second extra entry (``d`` → toggle_delegate)
        for the delegation feature. The locked F1..F10 row stays at
        10 and the locked single-key row stays at 8. The time-stop
        feature is reachable both via the ``#pause-button`` widget
        in the header and via the ``P`` keypress.
        """
        assert len(HtopTycoonApp.BINDINGS) == 20

    def test_app_bindings_first_ten_match_f_bindings(self) -> None:
        """The first 10 entries match the T24 ``register_f_bindings()`` output."""
        registry_f = register_f_bindings()
        assert HtopTycoonApp.BINDINGS[:10] == registry_f

    def test_app_bindings_middle_eight_match_single_key_bindings(self) -> None:
        """The middle 8 entries (10..18) match ``register_single_key_bindings()``.

        Renamed from ``last_eight_match_single_key_bindings`` when
        Wave 7 added the 19th entry (uppercase ``P``). Wave 8 then
        added the 20th entry (``d``). The single-key block stays at
        indices 10..17 (length 8); the extras live at indices
        18..19.
        """
        registry_sk = register_single_key_bindings()
        assert HtopTycoonApp.BINDINGS[10:18] == registry_sk

    def test_app_bindings_last_entries_are_extras(self) -> None:
        """The last 2 entries are the Wave-7/8 extra bindings.

        Asserts the exact ``Binding`` slice (so a future refactor
        that silently drops or reorders the extras fails loudly) and
        pins the individual keys/actions at indices 18 (pause) and
        19 (delegate).
        """
        from htop_tycoon.bindings.registry import register_extra_bindings

        registry_extra = register_extra_bindings()
        assert HtopTycoonApp.BINDINGS[18:] == registry_extra
        assert HtopTycoonApp.BINDINGS[18].key == "p"
        assert HtopTycoonApp.BINDINGS[18].action == "toggle_pause"
        assert HtopTycoonApp.BINDINGS[19].key == "d"
        assert HtopTycoonApp.BINDINGS[19].action == "toggle_delegate"


# -- App: action_* methods exist for every single-key binding --------------


class TestAppActionMethods:
    """Every bound single-key action has a corresponding ``action_*`` method."""

    def test_all_eight_single_key_action_methods_exist(self) -> None:
        """For each single-key binding, the App has ``action_<name>``.

        Iterates ``BINDINGS[10:18]`` (the T25 single-key block at length
        8) plus the 19th entry (backtick → toggle_pause, Wave 7) so
        every active action method is exercised.
        """
        for binding in (*HtopTycoonApp.BINDINGS[10:18], HtopTycoonApp.BINDINGS[18]):
            method_name = f"action_{binding.action}"
            assert hasattr(HtopTycoonApp, method_name), (
                f"missing {method_name} on HtopTycoonApp"
            )
            assert callable(getattr(HtopTycoonApp, method_name))

    def test_toggle_pause_action_method_exists(self) -> None:
        """The App has an ``action_toggle_pause`` method.

        Wave 7: the pause feature is reachable via both affordances —
        the ``#pause-button`` UI button (click handler in
        ``on_button_pressed``) and the ``P`` keyboard shortcut (the
        19th ``BINDINGS`` entry). Both paths share the same
        ``action_toggle_pause`` method.
        """
        assert hasattr(HtopTycoonApp, "action_toggle_pause")
        assert callable(HtopTycoonApp.action_toggle_pause)


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

    async def test_s_triggers_action_sort_by_salary(self) -> None:
        """Given: a mounted app
        When:  pilot.press('s') fires
        Then:  action_sort_by_salary records itself and notifies.

        Wave 7: ``s`` replaced ``p`` so the uppercase ``P`` shortcut
        for pause/resume doesn't collide. The lowercase ``s`` is
        mnemonic for "salary" and doesn't conflict with any other
        single-key binding.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app._notifications)
            await pilot.press("s")
            await pilot.pause()
            assert app._last_action == "sort_by_salary"  # type: ignore[attr-defined]
            assert len(app._notifications) > before

    async def test_i_triggers_action_sort_by_time_stub(self) -> None:
        """Given: a mounted app
        When:  pilot.press('i') fires
        Then:  action_sort_by_time records itself and notifies.

        Wave 7: ``i`` replaced the original ``T`` (uppercase shift+t)
        for sort_by_time. ``i`` is a mnemonic for "i/psa" = hired
        (the Korean label ``입사``). ``t`` was already taken by
        ``toggle_tree`` so the lowercase slot for time had to move
        to a different letter. The locked tuple now reads
        ``("i", "sort_by_time")``.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app._notifications)
            await pilot.press("i")
            await pilot.pause()
            assert app._last_action == "sort_by_time"  # type: ignore[attr-defined]
            assert len(app._notifications) > before


# -- Pilot: cursor up/down move the table cursor -------------------------


class TestCursorUpDown:
    """Pressing ``up`` / ``down`` moves the table cursor (no-op until table mounted)."""

    async def test_up_moves_employee_table_cursor(self) -> None:
        """Pressing Up moves the EmployeeTable cursor up.

        With priority promotion filtering out navigation keys, the
        EmployeeTable (which has focus by default after on_mount)
        receives the Up keypress via its built-in ``action_cursor_up``
        — the cursor moves to the row above. Previously the App's
        priority binding intercepted and ran its own ``action_cursor_up``
        that recorded ``_last_action``; now the table's own handler
        wins, which is the user-facing behavior we care about.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            from htop_tycoon.ui.widgets.employee_table import EmployeeTable
            table = app.query_one(EmployeeTable)
            # Move down once so we can move up
            await pilot.press("down")
            await pilot.pause()
            assert table.cursor_coordinate.row == 1
            await pilot.press("up")
            await pilot.pause()
            assert table.cursor_coordinate.row == 0

    async def test_down_moves_employee_table_cursor(self) -> None:
        """Pressing Down moves the EmployeeTable cursor down.

        See ``test_up_moves_employee_table_cursor`` for the contract
        change: navigation keys are no longer priority-promoted so the
        table's built-in handler wins.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            from htop_tycoon.ui.widgets.employee_table import EmployeeTable
            table = app.query_one(EmployeeTable)
            assert table.cursor_coordinate.row == 0
            await pilot.press("down")
            await pilot.pause()
            assert table.cursor_coordinate.row == 1


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


def test_registry_module_exposes_all_three_registry_functions() -> None:
    """All three registry functions are present (F-row + single-key + extra)."""
    import htop_tycoon.bindings.registry as reg

    assert callable(getattr(reg, "register_f_bindings", None))
    assert callable(getattr(reg, "register_single_key_bindings", None))
    assert callable(getattr(reg, "register_extra_bindings", None))


# -- Wave 7: p pause/resume keyboard shortcut -----------------------------


class TestPPauseShortcut:
    """The lowercase ``p`` key toggles pause/resume via the BINDINGS table.

    Wave 7: ``p`` is bound to ``action_toggle_pause`` via
    :func:`register_extra_bindings`. The same method is also invoked
    by the ``#pause-button`` click handler, so the keyboard path and
    the mouse path converge on a single state machine.

    Wave 7 amendment chain:
    - Original binding was backtick (rejected for tmux key-name issues).
    - Then ``P`` (uppercase shift+p) was paired with sort_by_salary
      moving to ``s`` (mnemonic for "salary").
    - Now lowercase ``p`` is used directly so all shortcuts are
      lowercase; ``P`` was freed up because the user requested
      lowercase-only keys.
    """

    async def test_p_keypress_flips_paused(self) -> None:
        """Pressing ``p`` flips ``_paused`` False → True → False.

        Verifies that the BINDINGS dispatcher routes the keypress to
        ``action_toggle_pause`` (the same method the ``#pause-button``
        click invokes), so the keyboard and mouse affordances stay in
        sync.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app._paused is False
            await pilot.press("p")
            await pilot.pause()
            assert app._paused is True, "first p press should pause"
            await pilot.press("p")
            await pilot.pause()
            assert app._paused is False, "second p press should resume"

    async def test_p_keypress_updates_button_label(self) -> None:
        """Pressing ``p`` flips the #pause-button label and CSS class.

        Confirms the keypress reaches ``action_toggle_pause`` (which
        delegates to ``_refresh_pause_button_label`` + ``_update_header_pause_indicator``)
        — not some other code path — so the visible cues stay in lockstep.
        """
        from textual.widgets import Button

        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            btn = app.query_one("#pause-button", Button)
            assert "일시정지" in str(btn.label)
            assert btn.has_class("is-paused") is False
            await pilot.press("p")
            await pilot.pause()
            assert "재생" in str(btn.label)
            assert btn.has_class("is-paused") is True

    async def test_p_keypress_does_not_push_quit_modal(self) -> None:
        """Pressing ``p`` must NOT push the F10 QuitOrSellScreen modal.

        Regression guard for the Wave 7 bug where ``action_toggle_pause``
        copy-pasted ``action_quit_or_sell``'s body and pushed the
        modal — the user's click on the pause button (or ``p``
        press) was immediately covered by the quit dialog, hiding
        the very state change they triggered.
        """
        from htop_tycoon.ui.screens.quit_or_sell import QuitOrSellScreen

        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert len(app.screen_stack) == 1
            await pilot.press("p")
            await pilot.pause()
            assert len(app.screen_stack) == 1, (
                "p must not push a modal — QuitOrSellScreen"
            )
            assert not any(
                isinstance(s, QuitOrSellScreen) for s in app.screen_stack
            )

    async def test_p_keypress_updates_header_indicator(self) -> None:
        """Pressing ``p`` adds/removes the ``⏸ 일시정지`` prefix on #header.

        Asserts the cross-cue sync: button label flips AND header prefix
        flips on the same keypress, so the user sees two visible cues
        instead of one.
        """
        from htop_tycoon.ui.widgets.header import GameHeader

        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Fire one tick so the header has a state to render against.
            app._tick_once()
            await pilot.pause()
            header = app.query_one("#header", GameHeader)
            assert "일시정지" not in str(header.renderable), (
                "before pause: header should not show the prefix"
            )
            await pilot.press("p")
            await pilot.pause()
            assert "⏸ 일시정지" in str(header.renderable), (
                "after pause: header should show '⏸ 일시정지' prefix"
            )
            await pilot.press("p")
            await pilot.pause()
            assert "일시정지" not in str(header.renderable), (
                "after resume: header prefix should be gone"
            )
