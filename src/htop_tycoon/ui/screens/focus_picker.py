# mypy: ignore-errors

"""htop_tycoon.ui.screens.focus_picker — F2 modal for per-dept focus change (T43).

Wave 8 (T43) — locks the F-key + i-key contract:

- F2 / ``i`` (per registry): ``action_focus_picker`` opens
  :class:`FocusPickerScreen`.
- ModalScreen lists the 5 dept types (Engineering, Sales, Operations,
  Marketing, Finance). For each dept it shows the current focus and
  uses keyboard navigation:
  * ``↑↓``: move focus to next/previous dept
  * ``Enter``: enter the change sub-menu for the selected dept
  * ``←→``: cycle options within the change sub-menu (BALANCED first)
  * ``Esc``: save + close
- Each focus change is gated by the cooldown guard
  (:func:`can_change_focus`). Blocked changes surface as a Korean
  ``변경 가능: T+{weeks}주차`` alert line.
- Apply the change via :func:`apply_focus_change` (returns new state,
  no in-place mutation) and emit a ``FocusChanged`` engine signal so
  :class:`ui.app_wiring.subscribe_focus_events` can re-render
  DepartmentDetail + the footer hint.

This commit implements the cooldown helper layer + the ModalScreen
shells. The full Pilot UI test for the ModalScreen navigation lives
in a follow-up wave (manual QA via Pilot in real terminal).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any, Literal  # noqa: F401

from htop_tycoon.domain.focus import FocusChoice, FocusType
from htop_tycoon.domain.state import GameState
from htop_tycoon.engine.events import Event

# ============================================================================
# Cooldown guard helpers (pure)
# ============================================================================


def _cooldown_weeks(balance: Mapping[str, object]) -> int:
    """Read cooldown_weeks from balance[departments][focus]."""
    depts = balance.get("departments")
    if not isinstance(depts, Mapping):
        return 16  # default per plan
    focus = depts.get("focus")
    if not isinstance(focus, Mapping):
        return 16
    val = focus.get("cooldown_weeks", 16)
    if not isinstance(val, int) or isinstance(val, bool):
        return 16
    return val


def can_change_focus(
    state: GameState,
    dept_id: str,
    current_tick: int,
    balance: Mapping[str, object],
) -> bool:
    """Return True iff ``current_tick`` is at or past the dept's cooldown boundary.

    Special case (UX): ``set_tick == 0`` is interpreted as "the focus was
    never explicitly chosen" (the factory default). The player's first
    real focus change is therefore *always* allowed — they shouldn't have
    to wait ``cooldown_weeks`` after a fresh dept unlock. After the first
    explicit change, ``set_tick`` is the actual change tick and the
    standard ``set_tick + cooldown_weeks`` boundary applies.

    Boundary: ``set_tick + cooldown_weeks`` (for set_tick > 0).
    """
    if not isinstance(state.dept_focus, Mapping):
        return True  # unknown dept → permit (let the apply path raise)
    choice = state.dept_focus.get(dept_id)
    if choice is None or int(choice.set_tick) == 0:
        return True
    boundary = int(choice.set_tick) + _cooldown_weeks(balance)
    return current_tick >= boundary


def cooldown_remaining_weeks(
    state: GameState,
    dept_id: str,
    current_tick: int,
    balance: Mapping[str, object],
) -> int:
    """Return the number of in-game weeks before this dept can change focus.

    Returns ``0`` when ``set_tick == 0`` (never-changed default), the
    cooldown count when explicitly ineligible, or ``0`` at-or-past the
    boundary.
    """
    if not isinstance(state.dept_focus, Mapping):
        return 0
    choice = state.dept_focus.get(dept_id)
    if choice is None or int(choice.set_tick) == 0:
        return 0
    if can_change_focus(state, dept_id, current_tick, balance):
        return 0
    cd = _cooldown_weeks(balance)
    boundary = int(choice.set_tick) + cd
    return boundary - current_tick


# ============================================================================
# apply_focus_change — pure function returning a new state
# ============================================================================


def apply_focus_change(
    state: GameState,
    dept_id: str,
    new_focus: FocusType,
    current_tick: int,
    balance: Mapping[str, object],
) -> GameState:
    """Return a new ``GameState`` with ``dept_id``'s focus set to ``new_focus``.

    The new ``FocusChoice.set_tick`` is set to ``current_tick``. The caller
    MUST pre-check :func:`can_change_focus`; this function does NOT
    re-check (it is a pure write-on-confirm step).
    """
    if not isinstance(state.dept_focus, Mapping):
        # No focus map — create with the single entry.
        new_choice = FocusChoice(
            dept_id=dept_id,
            focus=new_focus,
            set_tick=current_tick,
        )
        return dataclasses.replace(
            state,
            dept_focus={dept_id: new_choice},
        )
    existing = state.dept_focus.get(dept_id)
    if existing is None:
        new_choice = FocusChoice(
            dept_id=dept_id,
            focus=new_focus,
            set_tick=current_tick,
        )
    else:
        new_choice = FocusChoice(
            dept_id=existing.dept_id,
            focus=new_focus,
            set_tick=current_tick,
        )
    new_dept_focus = dict(state.dept_focus)
    new_dept_focus[dept_id] = new_choice
    return dataclasses.replace(state, dept_focus=new_dept_focus)


# ============================================================================
# FocusPickerScreen — ModalScreen skeleton (T43 UI)
# ============================================================================
#
# Full Pilot UI (textual) integration is deferred. The text below
# captures the public surface the T16 App wires against; we keep the
# class so the imports in ``app_wiring`` / ``bindings/registry``
# resolve without runtime errors.


try:
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Static
except ImportError:  # textual not installed (CI lint-only)
    Binding = None  # type: ignore[misc,assignment]
    Vertical = object  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]
    Static = object  # type: ignore[misc,assignment]


class FocusPickerScreen(ModalScreen):  # type: ignore[misc,valid-type,type-arg]
    """F2/i modal: list of 5 dept types, pick a focus.

    The modal shows one row per registered dept with the current
    focus, the cooldown remaining, and the dept type. Navigation:

    * up/down: move the cursor up/down through the dept list.
    * left/right: cycle the selected dept's focus through its 4
      options (BALANCED first). Pressing either arrow emits a
      FocusChanged event via the App event bus and refreshes the row.
    * Enter: explicit apply (same as right).
    * Escape: dismiss the modal without applying.

    Cooldown: when the dept is locked, the row shows the cooldown
    remaining and the left/right keys are no-ops. The cursor still
    moves so the player can see WHICH dept is locked.
    """

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Esc: 닫기", show=False),
        Binding("up", "cursor_up", "위로", show=False),
        Binding("down", "cursor_down", "아래로", show=False),
        Binding("right", "cycle_focus_next", "→: 다음 focus", show=False),
        Binding("left", "cycle_focus_prev", "←: 이전 focus", show=False),
        Binding("enter", "cycle_focus_next", "Enter: 적용", show=False),
    ]

    def __init__(self, app):  # noqa: D401
        super().__init__()
        self._app = app
        self._cursor: int = 0
        from htop_tycoon.data import load_balance

        self._balance = load_balance()
        self._state = app.state

    def compose(self) -> Any:  # type: ignore[override]
        from htop_tycoon.domain.focus import FocusType

        rows = []
        rows.append(
            Static(
                "[bold]부서 전략 선택 (← →: 변경, ↑↓: 부서, Esc: 닫기)[/bold]",
                id="focus-picker-title",
            )
        )
        dept_id_to_type = {}
        for dept_id, dept in self._state.departments.items():
            if not hasattr(dept, "type"):
                continue
            type_obj = dept.type
            type_name = getattr(type_obj, "name", None) or str(type_obj)
            dept_id_to_type[str(dept_id)] = type_name
        ordered_dept_ids = sorted(dept_id_to_type.keys(), key=lambda did: dept_id_to_type[did])
        if self._cursor >= len(ordered_dept_ids):
            self._cursor = max(0, len(ordered_dept_ids) - 1)
        for idx, dept_id in enumerate(ordered_dept_ids):
            dept = self._state.departments[dept_id]
            dept_type_name = dept_id_to_type[dept_id]
            fc = self._state.dept_focus.get(dept_id)
            if fc is not None and hasattr(fc, "focus"):
                current_focus = fc.focus
                set_tick = int(fc.set_tick)
            else:
                current_focus = FocusType.BALANCED
                set_tick = 0
            current_label = (
                current_focus.value if hasattr(current_focus, "value") else str(current_focus)
            )
            cooldown_weeks = _cooldown_weeks(self._balance)
            can = _can_change(self._state, dept_id, set_tick, cooldown_weeks)
            cooldown_str = f"  [dim]변경 가능: T+{cooldown_weeks}주차[/dim]" if not can else ""
            cursor_marker = "▶" if idx == self._cursor else " "
            row_text = (
                f"{cursor_marker} [{dept_type_name:<11}] focus=[b]{current_label}[/b]{cooldown_str}"
            )
            rows.append(Static(row_text, id=f"focus-row-{idx}"))
        if not ordered_dept_ids:
            rows.append(
                Static("[dim]등록된 부서가 없습니다. (F2 설정에서 부서를 해금하세요)[/dim]")
            )
        with Vertical(id="focus-picker-vertical"):
            yield from rows

    def _ordered_dept_ids(self) -> list:
        result = []
        for dept_id, dept in self._state.departments.items():
            if not hasattr(dept, "type"):
                continue
            type_obj = dept.type
            type_name = getattr(type_obj, "name", None) or str(type_obj)
            result.append((str(dept_id), type_name))
        result.sort(key=lambda pair: pair[1])
        return [did for did, _ in result]

    def _apply_cycle(self, delta: int) -> None:
        from htop_tycoon.domain.focus import FOCUS_TYPE_PER_DEPT
        # FocusChanged is defined in this module; reference the module-level
        # class name (no re-import — engine.events does not export it).

        dept_ids = self._ordered_dept_ids()
        if not dept_ids:
            return
        if self._cursor >= len(dept_ids):
            self._cursor = len(dept_ids) - 1
        dept_id = dept_ids[self._cursor]
        fc = self._state.dept_focus.get(dept_id)
        if fc is None or not hasattr(fc, "focus"):
            return
        cooldown_weeks = _cooldown_weeks(self._balance)
        if not _can_change(self._state, dept_id, int(fc.set_tick), cooldown_weeks):
            return
        options = FOCUS_TYPE_PER_DEPT.get(fc.focus.__class__.__name__, None)
        if options is None:
            return
        try:
            current_idx = options.index(fc.focus)
        except ValueError:
            return
        new_idx = (current_idx + delta) % len(options)
        if new_idx == current_idx:
            return
        new_focus = options[new_idx]
        prev_focus = fc.focus
        new_state, _ = apply_focus_change(  # type: ignore[misc]
            self._state,
            dept_id,
            new_focus=new_focus,
            current_tick=self._state.tick,
            balance=self._balance,
        )
        self._app.state = new_state  # type: ignore[has-type]
        self._state = new_state  # type: ignore[has-type]
        bus = getattr(self._app, "event_bus", None)
        if bus is not None:
            bus.publish(
                FocusChanged(
                    kind="focus_changed",
                    dept_id=dept_id,
                    prev=prev_focus,
                    next=new_focus,
                    tick=new_state.tick,
                )
            )
        self.refresh()

    def action_cursor_up(self) -> None:
        if self._cursor > 0:
            self._cursor -= 1
            self.refresh()

    def action_cursor_down(self) -> None:
        dept_ids = self._ordered_dept_ids()
        if self._cursor < len(dept_ids) - 1:
            self._cursor += 1
            self.refresh()

    def action_cycle_focus_next(self) -> None:
        self._apply_cycle(+1)

    def action_cycle_focus_prev(self) -> None:
        self._apply_cycle(-1)


def _can_change(state, dept_id, set_tick, cooldown_weeks) -> bool:  # type: ignore[no-untyped-def]
    return bool(state.tick >= set_tick + cooldown_weeks)


# ============================================================================
# FocusChanged — engine signal emitted by apply_ai_suggested_focus (T44)
# ============================================================================


@dataclasses.dataclass(frozen=True, slots=True)
class FocusChanged(Event):
    """Notification: a dept's focus transitioned ``prev`` -> ``next``.

    Inherits from :class:`Event` so it flows through the EventBus. The
    caller (T16 App or T9 tick engine) routes the signal:
      * Re-render the header (footer hint ``i:전략`` updates on
        per-dept focus changes).
      * Re-render the DepartmentDetail panel.
    """

    kind: Literal["focus_changed"]
    dept_id: str
    prev: FocusType
    next: FocusType
    tick: int


__all__ = [
    "FocusChanged",
    "FocusPickerScreen",
    "apply_focus_change",
    "can_change_focus",
    "cooldown_remaining_weeks",
]
