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
from typing import Any

from htop_tycoon.domain.focus import FocusChoice, FocusType
from htop_tycoon.engine.events import Event
from htop_tycoon.domain.state import GameState

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
    from textual.screen import ModalScreen
except ImportError:  # textual not installed (CI lint-only)
    Binding = None  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]


class FocusPickerScreen(ModalScreen):  # type: ignore[misc,valid-type,type-arg]
    """F2/i modal: list of 5 dept types, pick a focus.

    The full Pilot-rendered ``compose()`` / key-handlers live in a
    follow-up wave. The T43 commit ships the cooldown guards (the
    deterministic semantic) and the ModalScreen placeholder so the
    ``i`` binding can resolve.
    """

    BINDINGS = []  # populated when textual is available

    def __init__(self, app: Any) -> None:  # noqa: D401
        super().__init__()
        self._app = app




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
