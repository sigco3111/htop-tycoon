"""Tests for the T44 regime-aware Auto-Manager focus heuristic.

Wave 8 (T44) — engine extension that the AutoManager (``engine.ai_manager``)
will invoke when the player enables Auto-Manager (state._delegated).
This commit ships the heuristic + the apply function in two pure
helpers, decoupled from the full ``ai_manager`` module so the unit
tests stay focused and the existing AutoManager can drop in the
callsite later without restructuring.

Rules (locked):
- CRISIS regime + cash < 5000 → suggest COST / HEDGE / CONSERVATIVE_FIN
  (cost-like focus on every dept with a free slot).
- BOOM regime + cash > 50000 → suggest SPEED / AGGRESSIVE / GROWTH.
- NORMAL → BALANCED (no suggestion).
- The apply function respects the T43 cooldown guard — it only
  applies a focus change when ``can_change_focus`` permits.
"""

from __future__ import annotations

from typing import Any

from htop_tycoon.data import load_balance
from htop_tycoon.domain.dept import Department, DepartmentId, DepartmentType
from htop_tycoon.domain.focus import FocusChoice, FocusType
from htop_tycoon.domain.regimes import RegimeState, RegimeType
from htop_tycoon.domain.state import new_game
from htop_tycoon.engine.ai_focus_policy import (
    apply_ai_suggested_focus,
    regime_aware_focus_suggestion,
)

# ============================================================================
# Helpers
# ============================================================================


def _state_with_depts(
    *,
    regime: RegimeType,
    cash: int,
    dept_specs: list[tuple[str, DepartmentType, FocusType]],
) -> Any:
    """Build a state with one or more departments + focus choices.

    ``dept_specs`` is a list of (id_str, dept_type, focus).
    """
    from dataclasses import replace

    state = new_game(rng_seed=42)
    state = replace(
        state,
        company=replace(state.company, cash=cash, market_cap=cash),
        regime=RegimeState(current=regime, weeks_in_regime=0, started_tick=0),
    )
    departments: dict[Any, Any] = {}
    dept_focus: dict[Any, Any] = {}
    for did_str, dt, focus in dept_specs:
        did = DepartmentId(did_str)
        departments[did] = Department(
            id=did,
            type=dt,
            employee_ids=[],
            head_employee_id=None,
            founded_tick=0,
        )
        dept_focus[did] = FocusChoice(dept_id=did, focus=focus, set_tick=0)
    return replace(state, departments=departments, dept_focus=dept_focus)


# ============================================================================
# regime_aware_focus_suggestion
# ============================================================================


class TestRegimeAwareFocusSuggestion:
    def test_crisis_low_cash_suggests_cost_like_focus(self) -> None:
        balance = load_balance()
        state = _state_with_depts(
            regime=RegimeType.CRISIS,
            cash=2000,
            dept_specs=[
                ("dept-eng-1", DepartmentType.Engineering, FocusType.BALANCED),
            ],
        )
        suggestion = regime_aware_focus_suggestion(state, "dept-eng-1", balance)
        # CRISIS + low cash: should pick a cost-like focus (COST/Engineering).
        assert suggestion is FocusType.COST

    def test_boom_high_cash_suggests_growth_focus(self) -> None:
        balance = load_balance()
        state = _state_with_depts(
            regime=RegimeType.BOOM,
            cash=100_000,
            dept_specs=[
                ("dept-eng-1", DepartmentType.Engineering, FocusType.BALANCED),
            ],
        )
        suggestion = regime_aware_focus_suggestion(state, "dept-eng-1", balance)
        # BOOM + high cash + Engineering: should pick a growth-y focus.
        assert suggestion is FocusType.SPEED

    def test_normal_regime_returns_balanced(self) -> None:
        balance = load_balance()
        state = _state_with_depts(
            regime=RegimeType.NORMAL,
            cash=50_000,
            dept_specs=[
                ("dept-eng-1", DepartmentType.Engineering, FocusType.BALANCED),
            ],
        )
        assert regime_aware_focus_suggestion(state, "dept-eng-1", balance) is FocusType.BALANCED

    def test_crisis_high_cash_still_suggests_cost(self) -> None:
        """CRISIS bias is regime-driven, not cash-driven. Even with
        high cash, CRISIS suggests cost-like focus (conservative).
        """
        balance = load_balance()
        state = _state_with_depts(
            regime=RegimeType.CRISIS,
            cash=100_000,  # high cash
            dept_specs=[
                ("dept-eng-1", DepartmentType.Engineering, FocusType.BALANCED),
            ],
        )
        suggestion = regime_aware_focus_suggestion(state, "dept-eng-1", balance)
        # CRISIS at high cash still picks COST — regime dominates.
        assert suggestion is FocusType.COST


# ============================================================================
# apply_ai_suggested_focus — respects cooldown
# ============================================================================


class TestApplyAISuggestedFocus:
    def test_no_change_when_suggestion_is_balanced(self) -> None:
        """NORMAL regime suggests BALANCED — apply is a no-op (no
        cooldown burn).
        """
        balance = load_balance()
        state = _state_with_depts(
            regime=RegimeType.NORMAL,
            cash=50_000,
            dept_specs=[
                ("dept-eng-1", DepartmentType.Engineering, FocusType.BALANCED),
            ],
        )
        new_state, signals = apply_ai_suggested_focus(state, balance, current_tick=0)
        assert new_state.dept_focus["dept-eng-1"].focus is FocusType.BALANCED
        assert signals == []

    def test_change_applied_when_cooldown_permits(self) -> None:
        balance = load_balance()
        state = _state_with_depts(
            regime=RegimeType.CRISIS,
            cash=2000,
            dept_specs=[
                ("dept-eng-1", DepartmentType.Engineering, FocusType.BALANCED),
            ],
        )
        # set_tick=0 (never changed) → cooldown allows.
        new_state, signals = apply_ai_suggested_focus(state, balance, current_tick=0)
        # Focus should now be COST.
        assert new_state.dept_focus["dept-eng-1"].focus is FocusType.COST
        assert len(signals) == 1

    def test_change_skipped_when_cooldown_blocks(self) -> None:
        balance = load_balance()
        from dataclasses import replace

        state = _state_with_depts(
            regime=RegimeType.CRISIS,
            cash=2000,
            dept_specs=[
                ("dept-eng-1", DepartmentType.Engineering, FocusType.BALANCED),
            ],
        )
        # Force set_tick to 100 (well in cooldown at current_tick=10).
        did = DepartmentId("dept-eng-1")
        state = replace(
            state,
            dept_focus={did: FocusChoice(dept_id=did, focus=FocusType.BALANCED, set_tick=100)},
        )
        new_state, signals = apply_ai_suggested_focus(state, balance, current_tick=10)
        assert new_state.dept_focus["dept-eng-1"].focus is FocusType.BALANCED
        assert signals == [], "cooldown should block the AI's suggestion"
