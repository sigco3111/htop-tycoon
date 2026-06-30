"""Tests for the T41 apply_focus_modifier pure function.

Wave 8 (T41) — the engine function that combines the per-department
focus modifier with the active regime's multiplier, then clamps to
the safe range [0.5, 2.0].

Contract:
- BALANCED focus returns exactly 1.0 in all three metrics.
- ``productivity`` is multiplied by the regime's
  ``revenue_multiplier``; ``salary_growth`` by
  ``salary_growth_multiplier``; ``satisfaction_delta`` is NOT
  scaled (it's a per-tick int delta, regime doesn't moderate it).
- The final modifier is clamped to [0.5, 2.0] to prevent runaway
  compounding with the regime's own multipliers (e.g., SPEED 1.15
  × CRISIS salary_growth 0.85 = 0.7225, well inside bounds).
- Unknown dept_id / unknown focus returns 1.0 + warn-once log (defensive).
- Pure: no state mutation; no ``event_bus.publish``.
"""

from __future__ import annotations

from typing import Any

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.focus import FocusChoice, FocusType
from htop_tycoon.domain.regimes import RegimeState, RegimeType
from htop_tycoon.domain.state import new_game, state_hash
from htop_tycoon.engine.dept_focus import (
    apply_focus_modifier,
    effective_modifier_clamp_max,
    effective_modifier_clamp_min,
)

# ============================================================================
# Helpers
# ============================================================================


def _state_with(
    focus: FocusType,
    regime: RegimeType = RegimeType.NORMAL,
    *,
    dept_id_str: str = "dept-eng-1",
) -> Any:
    """Build a GameState with the given focus pre-set for one dept."""
    from dataclasses import replace

    state = new_game(rng_seed=42)
    return replace(
        state,
        dept_focus={
            dept_id_str: FocusChoice(
                dept_id=dept_id_str, focus=focus, set_tick=0
            )
        },
        regime=RegimeState(
            current=regime, weeks_in_regime=0, started_tick=0
        ),
    )


# ============================================================================
# BALANCED is the universal identity
# ============================================================================


class TestBalancedIdentity:
    @pytest.mark.parametrize(
        "metric", ["productivity", "satisfaction_delta", "salary_growth"]
    )
    def test_balanced_returns_one(self, metric: str) -> None:
        balance = load_balance()
        state = _state_with(FocusType.BALANCED)
        result = apply_focus_modifier(state, "dept-eng-1", metric, balance)
        assert result == pytest.approx(1.0)


# ============================================================================
# Regime interaction
# ============================================================================


class TestRegimeInteraction:
    def test_speed_x_normal_productivity_is_1_15(self) -> None:
        balance = load_balance()
        state = _state_with(FocusType.SPEED, RegimeType.NORMAL)
        result = apply_focus_modifier(state, "dept-eng-1", "productivity", balance)
        assert result == pytest.approx(1.15)

    def test_speed_x_boom_productivity_clamped_to_safe_range(self) -> None:
        balance = load_balance()
        state = _state_with(FocusType.SPEED, RegimeType.BOOM)
        result = apply_focus_modifier(state, "dept-eng-1", "productivity", balance)
        assert result == pytest.approx(1.495)

    def test_cost_x_crisis_salary_growth_clamped(self) -> None:
        balance = load_balance()
        state = _state_with(FocusType.COST, RegimeType.CRISIS)
        result = apply_focus_modifier(state, "dept-eng-1", "salary_growth", balance)
        assert result == pytest.approx(0.7225)

    def test_satisfaction_delta_not_scaled_by_regime(self) -> None:
        balance = load_balance()
        state_normal = _state_with(FocusType.QUALITY, RegimeType.NORMAL)
        state_crisis = _state_with(FocusType.QUALITY, RegimeType.CRISIS)
        normal_val = apply_focus_modifier(
            state_normal, "dept-eng-1", "satisfaction_delta", balance
        )
        crisis_val = apply_focus_modifier(
            state_crisis, "dept-eng-1", "satisfaction_delta", balance
        )
        assert normal_val == crisis_val
        assert normal_val == pytest.approx(2.0)


# ============================================================================
# Clamp behaviour
# ============================================================================


class TestClamp:
    def test_clamp_bounds_read_from_balance(self) -> None:
        # Trigger lazy load; even unused here, balance load populates
        # the module-level cache.
        load_balance()
        assert effective_modifier_clamp_min() == pytest.approx(0.5)
        assert effective_modifier_clamp_max() == pytest.approx(2.0)

    def test_unknown_dept_id_returns_one(self) -> None:
        balance = load_balance()
        state = new_game(rng_seed=42)
        result = apply_focus_modifier(
            state, "dept-does-not-exist", "productivity", balance
        )
        assert result == pytest.approx(1.0)


# ============================================================================
# Pure-function invariant
# ============================================================================


class TestPurity:
    def test_state_not_mutated(self) -> None:
        balance = load_balance()
        state = _state_with(FocusType.SPEED, RegimeType.BOOM)
        hash_before = state_hash(state)
        _ = apply_focus_modifier(state, "dept-eng-1", "productivity", balance)
        assert state_hash(state) == hash_before, "input state must not mutate"
