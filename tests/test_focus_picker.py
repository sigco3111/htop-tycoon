"""Tests for the T43 FocusPickerScreen + cooldown behavior.

Wave 8 (T43) — the engine-level cooldown guard for focus changes.

The ModalScreen (FocusPickerScreen in ui/screens/focus_picker.py) uses
two pure helpers from this module:

  * ``can_change_focus(state, dept_id, current_tick, balance) -> bool``
    — returns True if ``current_tick - set_tick >= cooldown_weeks``, OR
    if the dept has never been explicitly configured (set_tick == 0).
  * ``apply_focus_change(state, dept_id, new_focus, current_tick)``
    — returns a new ``GameState`` with the focus replaced AND
    ``set_tick`` updated to ``current_tick``.

Cooldown semantics (locked):
- The NEXT change is permitted when ``current_tick >= set_tick +
  cooldown_weeks``.
- Boundary ticks (== set_tick + cooldown_weeks) ARE permitted.
- A dept with ``set_tick == 0`` is treated as "never explicitly
  configured" so the player's first real change is NOT delayed.
"""

from __future__ import annotations

from typing import Any

from htop_tycoon.data import load_balance
from htop_tycoon.domain.dept import Department, DepartmentId, DepartmentType
from htop_tycoon.domain.focus import FocusChoice, FocusType
from htop_tycoon.domain.state import new_game, state_hash
from htop_tycoon.ui.screens.focus_picker import (
    FocusPickerScreen,
    apply_focus_change,
    can_change_focus,
    cooldown_remaining_weeks,
)

# ============================================================================
# Helpers
# ============================================================================


def _state_with(
    *,
    dept_id: str,
    dept_type: DepartmentType,
    focus: FocusType = FocusType.BALANCED,
    set_tick: int = 0,
    include_second_dept: bool = False,
    dept_b_id: str = "dept-sales-1",
    focus_b: FocusType = FocusType.BALANCED,
    set_tick_b: int = 0,
) -> Any:
    """Build a state with one (optionally two) dept(s) + focus choice(s)."""
    from dataclasses import replace

    state = new_game(rng_seed=42)
    d_a = DepartmentId(dept_id)
    departments = {
        d_a: Department(
            id=d_a,
            type=dept_type,
            employee_ids=[],
            head_employee_id=None,
            founded_tick=0,
        )
    }
    focus_map: dict[Any, Any] = {d_a: FocusChoice(dept_id=d_a, focus=focus, set_tick=set_tick)}
    if include_second_dept:
        d_b = DepartmentId(dept_b_id)
        departments[d_b] = Department(
            id=d_b,
            type=DepartmentType.Sales,
            employee_ids=[],
            head_employee_id=None,
            founded_tick=0,
        )
        focus_map[d_b] = FocusChoice(dept_id=d_b, focus=focus_b, set_tick=set_tick_b)
    return replace(state, departments=departments, dept_focus=focus_map)


# ============================================================================
# Cooldown guard
# ============================================================================


class TestCanChangeFocus:
    def test_first_change_allowed_when_set_tick_is_zero(self) -> None:
        """A dept with ``set_tick == 0`` (factory default) is
        immediately eligible. The player's first explicit focus
        change does not wait out the cooldown.
        """
        balance = load_balance()
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
            focus=FocusType.BALANCED,
            set_tick=0,
        )
        assert can_change_focus(state, "dept-eng-1", current_tick=0, balance=balance)
        assert can_change_focus(state, "dept-eng-1", current_tick=15, balance=balance)

    def test_change_blocked_within_cooldown(self) -> None:
        """After an explicit focus set (set_tick=10), the next eligible
        change is at tick=26 (10 + 16). Ticks 11..25 must be blocked.
        """
        balance = load_balance()
        cooldown_weeks = int(balance["departments"]["focus"]["cooldown_weeks"])
        assert cooldown_weeks == 16
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
            focus=FocusType.BALANCED,
            set_tick=10,
        )
        for t in range(11, 26):  # 11..25 inclusive
            assert not can_change_focus(state, "dept-eng-1", current_tick=t, balance=balance), (
                f"tick={t} unexpectedly allowed"
            )

    def test_change_at_cooldown_boundary_allowed(self) -> None:
        balance = load_balance()
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
            focus=FocusType.BALANCED,
            set_tick=10,
        )
        # boundary = set_tick + cooldown = 10 + 16 = 26
        assert can_change_focus(state, "dept-eng-1", current_tick=26, balance=balance)

    def test_change_after_cooldown_allowed(self) -> None:
        balance = load_balance()
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
            focus=FocusType.BALANCED,
            set_tick=10,
        )
        assert can_change_focus(state, "dept-eng-1", current_tick=100, balance=balance)


class TestCooldownRemainingWeeks:
    def test_remaining_weeks_when_within_cooldown(self) -> None:
        balance = load_balance()
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
            focus=FocusType.BALANCED,
            set_tick=10,
        )
        # current_tick=10, boundary=26, remaining=16.
        remaining = cooldown_remaining_weeks(state, "dept-eng-1", current_tick=10, balance=balance)
        assert remaining == 16

    def test_zero_when_set_tick_is_zero(self) -> None:
        balance = load_balance()
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
            focus=FocusType.BALANCED,
            set_tick=0,
        )
        assert cooldown_remaining_weeks(state, "dept-eng-1", current_tick=20, balance=balance) == 0

    def test_zero_when_past_boundary(self) -> None:
        balance = load_balance()
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
            focus=FocusType.BALANCED,
            set_tick=10,
        )
        assert cooldown_remaining_weeks(state, "dept-eng-1", current_tick=30, balance=balance) == 0


# ============================================================================
# apply_focus_change — pure function
# ============================================================================


class TestApplyFocusChange:
    def test_change_persists_and_updates_set_tick(self) -> None:
        balance = load_balance()
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
        )
        new_state = apply_focus_change(
            state,
            "dept-eng-1",
            new_focus=FocusType.QUALITY,
            current_tick=20,
            balance=balance,
        )
        new_choice = new_state.dept_focus["dept-eng-1"]
        assert new_choice.focus is FocusType.QUALITY
        assert new_choice.set_tick == 20

    def test_pure_no_input_mutation(self) -> None:
        balance = load_balance()
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
        )
        before = state_hash(state)
        _ = apply_focus_change(
            state,
            "dept-eng-1",
            new_focus=FocusType.SPEED,
            current_tick=20,
            balance=balance,
        )
        assert state_hash(state) == before, "input state must not mutate"


# ============================================================================
# Per-dept independent cooldown
# ============================================================================


class TestPerDeptCooldown:
    def test_independent_dept_cooldowns(self) -> None:
        """Cooldown is per-dept. Dept A had a recent change; Dept B
        (still at set_tick=0) is immediately eligible.
        """
        balance = load_balance()
        # Set dept-eng-1 with explicit set_tick=10.
        # Set dept-sales-1 with default set_tick=0 → always eligible.
        state = _state_with(
            dept_id="dept-eng-1",
            dept_type=DepartmentType.Engineering,
            focus=FocusType.SPEED,
            set_tick=10,
            include_second_dept=True,
            focus_b=FocusType.BALANCED,
            set_tick_b=0,
        )
        # At current_tick=6: dept-eng-1 set_tick=10, boundary=26 → 6<26 blocked.
        #                     dept-sales-1 set_tick=0 → always eligible.
        assert not can_change_focus(state, "dept-eng-1", current_tick=6, balance=balance)
        assert can_change_focus(state, "dept-sales-1", current_tick=6, balance=balance)


# ============================================================================
# ModalScreen shell existence
# ============================================================================


class TestFocusPickerScreenExists:
    def test_focus_picker_screen_class_importable(self) -> None:
        """Smoke test: the ModalScreen is importable. The full Pilot
        UI test is deferred to a follow-up wave (manual QA in real
        terminal).
        """
        assert isinstance(FocusPickerScreen, type)
        # The class must be a Textual ModalScreen.
        from textual.screen import ModalScreen as _ModalScreen

        assert issubclass(FocusPickerScreen, _ModalScreen)
