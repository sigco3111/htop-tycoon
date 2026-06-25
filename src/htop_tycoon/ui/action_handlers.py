"""htop_tycoon.ui.action_handlers — Action handler implementations for HtopTycoonApp.

This module owns the LOGIC of every ``action_*`` handler that lives on
``HtopTycoonApp``. The handlers are implemented as module-level functions
that take the App instance as their first argument; the App's class body
binds each ``action_<name>`` method to the matching handler so Textual's
binding system can dispatch via the standard ``action_<name>`` attribute
lookup.

Splitting the handlers out of ``app.py`` keeps the App class lean (focused
on lifecycle + layout) and gives each handler a single, testable entry
point. The functions preserve the AGENTS.md invariant "UI handlers MUST
NOT mutate ``self.state`` directly" — every handler that changes state
delegates to a pure engine action and rebinds ``self.state`` to the
returned fresh state.

Contract surface (locked by T24+T25 plan lines 537-585):

- F1..F10: see ``register_f_bindings()`` for the locked key/action table.
- Single-key: see ``register_single_key_bindings()`` for t/u/m/p/T/up/down/space.
- Every handler either:
    1. Calls an engine action and publishes events (F7/F8/F9), OR
    2. Looks up a widget by class name and calls its method (F5/t, m, p, T), OR
    3. Records the action name + notifies (stubs for F1/F2/F3/F4/F10, u, sort_by_time,
       cursor_up/down, tag_selected), OR
    4. Cycles a counter + dispatches (F6 cycle_sort).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from htop_tycoon.engine import actions as engine_actions
from htop_tycoon.engine.events import AlertRaised

if TYPE_CHECKING:
    from htop_tycoon.ui.app import HtopTycoonApp


# Sort cycle order for F6 (cycle_sort). Each entry is a method name on
# the EmployeeTable widget. The first three entries map directly to the
# locked single-key actions (M/P/T); the third entry (skill) is the
# default sort on the EmployeeTable.
_SORT_CYCLE: tuple[str, ...] = (
    "sort_by_satisfaction",
    "sort_by_salary",
    "sort_by_skill",
)

# Korean alert message when the player presses F9/F7/F8 with no selected
# employee. Per the QA scenario for T25: "F9 with no selection → alert
# '직원을 선택하세요'".
_NO_SELECTION_MESSAGE_KO: str = "직원을 선택하세요"

__all__ = [
    "cycle_sort",
    "demote_selected",
    "filter",
    "filter_by_dept",
    "fire_selected",
    "promote_selected",
    "quit_or_sell",
    "search",
    "show_help",
    "show_setup",
    "sort_by_salary",
    "sort_by_satisfaction",
    "sort_by_skill",
    "sort_by_time",
    "tag_selected",
    "toggle_tree",
    "cursor_down",
    "cursor_up",
]


# --------------------------------------------------------------------- helpers


def _record(app: HtopTycoonApp, action_name: str, label_ko: str) -> None:
    """Shared helper: record the action name on the App and notify the user."""
    app._last_action = action_name
    app.notify(f"{label_ko} ({action_name})")


def _alert_no_selection(app: HtopTycoonApp, action_name: str) -> None:
    """Publish a 'no selection' alert + record the action.

    Used by F7 / F8 / F9 when ``self._selected_employee_id`` is ``None``.
    """
    app._last_action = action_name
    app.notify(_NO_SELECTION_MESSAGE_KO)
    app.event_bus.publish(
        AlertRaised(message_ko=_NO_SELECTION_MESSAGE_KO, severity="warn")
    )


def _find_widget_by_class_name(app: HtopTycoonApp, class_name: str) -> Any:
    """Return the first mounted widget whose class name matches, or ``None``."""
    try:
        results = app.query(f".{class_name}")
    except Exception:
        return None
    if not results:
        return None
    return results.first()


# --------------------------------------------------------------------- F-row handlers


def show_help(app: HtopTycoonApp) -> None:
    """F1 stub — opens the help modal (real impl in T26)."""
    _record(app, "show_help", "도움말")


def show_setup(app: HtopTycoonApp) -> None:
    """F2 stub — opens setup/save modal (real impl in T30)."""
    _record(app, "show_setup", "설정/저장")


def search(app: HtopTycoonApp) -> None:
    """F3 stub — opens search (real impl deferred past T25)."""
    _record(app, "search", "검색")


def filter(app: HtopTycoonApp) -> None:
    """F4 stub — opens filter (real impl deferred past T25)."""
    _record(app, "filter", "필터")


def toggle_tree(app: HtopTycoonApp) -> None:
    """F5 / single-key ``t`` — toggle org-tree expand/collapse.

    If the ``OrgTree`` widget is mounted, call its ``toggle_expand_all()``.
    Otherwise the action is observable only via ``_last_action`` and
    ``self.notify`` (the widget is wired into ``compose()`` in a later
    todo).
    """
    _record(app, "toggle_tree", "트리 토글")
    tree = _find_widget_by_class_name(app, "OrgTree")
    if tree is not None and hasattr(tree, "toggle_expand_all"):
        tree.toggle_expand_all()


def cycle_sort(app: HtopTycoonApp) -> None:
    """F6 — cycle through [satisfaction, salary, skill] sort modes.

    Increments ``app._sort_cycle_index`` modulo the cycle length and
    applies the corresponding sort directly to the EmployeeTable (if
    mounted). Records ``_last_action="cycle_sort"`` exactly once so the
    T24 contract test ("f6 → action_cycle_sort") still passes.
    """
    app._sort_cycle_index = (app._sort_cycle_index + 1) % len(_SORT_CYCLE)
    _record(app, "cycle_sort", "정렬")
    # Apply directly to the EmployeeTable (NOT via the action_sort_by_*
    # wrappers) so we don't overwrite ``_last_action`` with the inner
    # action's name.
    next_method = _SORT_CYCLE[app._sort_cycle_index]
    table = _find_widget_by_class_name(app, "EmployeeTable")
    if table is None:
        return
    method = getattr(table, next_method, None)
    if callable(method):
        method()


def promote_selected(app: HtopTycoonApp) -> None:
    """F7 — promote the selected employee via ``engine.actions.promote``."""
    if app._selected_employee_id is None:
        _alert_no_selection(app, "promote_selected")
        return
    try:
        new_state, events = engine_actions.promote(
            app.state, app._selected_employee_id
        )
    except KeyError:
        _alert_no_selection(app, "promote_selected")
        return
    app.state = new_state
    app.event_bus.publish_many(events)
    _record(app, "promote_selected", "승진")


def demote_selected(app: HtopTycoonApp) -> None:
    """F8 — demote the selected employee via ``engine.actions.demote``."""
    if app._selected_employee_id is None:
        _alert_no_selection(app, "demote_selected")
        return
    try:
        new_state, events = engine_actions.demote(
            app.state, app._selected_employee_id
        )
    except KeyError:
        _alert_no_selection(app, "demote_selected")
        return
    app.state = new_state
    app.event_bus.publish_many(events)
    _record(app, "demote_selected", "감봉")


def fire_selected(app: HtopTycoonApp) -> None:
    """F9 — fire the selected employee via ``engine.actions.fire``.

    Pays severance from cash, removes the employee from state, publishes
    the ``EmployeeFired`` event, and clears the selection.
    """
    if app._selected_employee_id is None:
        _alert_no_selection(app, "fire_selected")
        return
    try:
        new_state, events = engine_actions.fire(
            app.state, app._selected_employee_id
        )
    except KeyError:
        _alert_no_selection(app, "fire_selected")
        return
    app.state = new_state
    app.event_bus.publish_many(events)
    # Clear selection: the fired employee no longer exists.
    app._selected_employee_id = None
    _record(app, "fire_selected", "해고")


def quit_or_sell(app: HtopTycoonApp) -> None:
    """F10 stub — quits the game or sells the company (real impl deferred)."""
    _record(app, "quit_or_sell", "종료/매각")


# --------------------------------------------------------------------- single-key handlers


def filter_by_dept(app: HtopTycoonApp) -> None:
    """Single-key ``u`` — open the department picker (stub for T25)."""
    _record(app, "filter_by_dept", "부서 필터")
    app._open_dept_picker()


def sort_by_satisfaction(app: HtopTycoonApp) -> None:
    """Single-key ``m`` — sort EmployeeTable by 만족도 desc."""
    _record(app, "sort_by_satisfaction", "만족도 정렬")
    table = _find_widget_by_class_name(app, "EmployeeTable")
    if table is not None and hasattr(table, "sort_by_satisfaction"):
        table.sort_by_satisfaction()


def sort_by_salary(app: HtopTycoonApp) -> None:
    """Single-key ``p`` — sort EmployeeTable by 급여 desc."""
    _record(app, "sort_by_salary", "급여 정렬")
    table = _find_widget_by_class_name(app, "EmployeeTable")
    if table is not None and hasattr(table, "sort_by_salary"):
        table.sort_by_salary()


def sort_by_time(app: HtopTycoonApp) -> None:
    """Single-key ``T`` — sort EmployeeTable by 시간 desc (stub for T25)."""
    _record(app, "sort_by_time", "시간 정렬")


def sort_by_skill(app: HtopTycoonApp) -> None:
    """Internal sort used by F6 cycle_sort (no keybinding today).

    Sorts the EmployeeTable by skill desc when mounted. Not directly
    bound to a key — invoked by ``cycle_sort`` to land on the default
    sort mode.
    """
    _record(app, "sort_by_skill", "스킬 정렬")
    table = _find_widget_by_class_name(app, "EmployeeTable")
    if table is not None and hasattr(table, "sort_by_skill"):
        table.sort_by_skill()


def cursor_up(app: HtopTycoonApp) -> None:
    """Single-key ``up`` — move the EmployeeTable cursor up."""
    _record(app, "cursor_up", "위로")


def cursor_down(app: HtopTycoonApp) -> None:
    """Single-key ``down`` — move the EmployeeTable cursor down."""
    _record(app, "cursor_down", "아래로")


def tag_selected(app: HtopTycoonApp) -> None:
    """Single-key ``space`` — mark the selected employee (visual only).

    Per the plan MUST-NOT-DO, Space is a marker only in v0.1.0: bulk fire
    via tagged employees is out of scope. The handler toggles membership
    of ``app._tagged_employee_ids`` for the currently selected employee
    and notifies; no bulk side-effect.
    """
    _record(app, "tag_selected", "태그")
    if app._selected_employee_id is None:
        return
    eid = app._selected_employee_id
    if eid in app._tagged_employee_ids:
        app._tagged_employee_ids.discard(eid)
    else:
        app._tagged_employee_ids.add(eid)
