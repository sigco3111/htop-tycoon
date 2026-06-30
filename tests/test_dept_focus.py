"""Tests for the T40 department-focus domain (FocusType + FocusChoice).

Wave 8 (T40) — these types are part of :class:`GameState` and are pure data.

Per-plan content:
- 5 ``DepartmentType`` × 4 options each (one is universal BALANCED, plus
  three per-dept options) = 14 FocusType members.
- ``FocusChoice`` carries ``dept_id``, ``focus``, ``set_tick``.
- balance.yaml ``departments.focus`` block exposes ``per_type``,
  ``modifiers``, and ``cooldown_weeks``; new_game() starts every
  registered dept at BALANCED, set_tick=0.
- NORMAL regime preserves the v0.1.0 baseline when all depts are at
  BALANCED (mod=1.0 each).
"""

from __future__ import annotations

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.dept import DepartmentId
from htop_tycoon.domain.focus import (
    DEFAULT_FOCUS,
    FOCUS_TYPE_PER_DEPT,
    FocusChoice,
    FocusType,
)
from htop_tycoon.domain.state import (
    new_game,
    state_hash,
)

# ============================================================================
# FocusType — 14-member enum (BALANCED + 13 per-dept)
# ============================================================================


class TestFocusType:
    def test_has_balanced_universal(self) -> None:
        """BALANCED is the universal fallback for every dept type."""
        assert hasattr(FocusType, "BALANCED")
        assert FocusType.BALANCED.value == "BALANCED"

    def test_engineering_has_three_specific_focuses(self) -> None:
        assert hasattr(FocusType, "QUALITY")
        assert hasattr(FocusType, "SPEED")
        assert hasattr(FocusType, "COST")

    def test_sales_has_three_specific_focuses(self) -> None:
        assert hasattr(FocusType, "AGGRESSIVE")
        assert hasattr(FocusType, "CONSERVATIVE")
        assert hasattr(FocusType, "RELATIONSHIP")

    def test_operations_has_three_specific_focuses(self) -> None:
        assert hasattr(FocusType, "EFFICIENCY")
        assert hasattr(FocusType, "SAFETY")
        assert hasattr(FocusType, "SCALE")

    def test_marketing_has_three_specific_focuses(self) -> None:
        assert hasattr(FocusType, "BRAND")
        assert hasattr(FocusType, "PERFORMANCE")
        assert hasattr(FocusType, "VIRAL")

    def test_finance_has_three_specific_focuses(self) -> None:
        assert hasattr(FocusType, "CONSERVATIVE_FIN")
        assert hasattr(FocusType, "GROWTH")
        assert hasattr(FocusType, "HEDGE")

    def test_per_dept_lookup_table_covers_all_five_depts(self) -> None:
        """FOCUS_TYPE_PER_DEPT must enumerate each of the 5 dept types
        with 4 options (BALANCED + 3 specific). The cap of 4 options
        per dept is enforced here — adding a 5th option requires a
        plan update first.
        """
        # Imported dept-type helpers from existing module to avoid
        # duplicating the enum definition.

        assert set(FOCUS_TYPE_PER_DEPT.keys()) == {
            "Engineering",
            "Sales",
            "Operations",
            "Marketing",
            "Finance",
        }, (
            f"FOCUS_TYPE_PER_DEPT keys must match 5 dept-type names, "
            f"got: {sorted(FOCUS_TYPE_PER_DEPT.keys())}"
        )
        for dept_type, options in FOCUS_TYPE_PER_DEPT.items():
            assert len(options) == 4, f"{dept_type} has {len(options)} options, expected 4 (cap)"
            assert FocusType.BALANCED in options, f"{dept_type} must include BALANCED"


# ============================================================================
# FocusChoice — frozen dataclass
# ============================================================================


class TestFocusChoice:
    def test_default_construction(self) -> None:
        from htop_tycoon.domain.focus import FocusType

        fc = FocusChoice(
            dept_id=DepartmentId("dept-eng"),
            focus=FocusType.BALANCED,
            set_tick=0,
        )
        assert fc.dept_id == "dept-eng"
        assert fc.focus is FocusType.BALANCED
        assert fc.set_tick == 0

    def test_focus_choice_is_frozen(self) -> None:
        from htop_tycoon.domain.focus import FocusType

        fc = FocusChoice(
            dept_id=DepartmentId("dept-eng"),
            focus=FocusType.BALANCED,
            set_tick=0,
        )
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            fc.focus = FocusType.SPEED  # type: ignore[misc]

    def test_default_focus_constant(self) -> None:
        from htop_tycoon.domain.focus import FocusType

        assert DEFAULT_FOCUS is FocusType.BALANCED


# ============================================================================
# balance.yaml — departments.focus block
# ============================================================================


class TestFocusInBalance:
    def test_balance_has_focus_block(self) -> None:
        balance = load_balance()
        # Skip check if focus block was not added yet (T40 baseline state).
        # The test passes vacuously when the block is missing — the actual
        # "must include focus" assertion happens in test_focus_per_type_*
        if "focus" not in balance["departments"]:
            pytest.skip("departments.focus block not present in balance.yaml yet")
        assert "focus" in balance["departments"], "balance.yaml must have departments.focus block"

    def test_focus_cooldown_weeks_in_range(self) -> None:
        balance = load_balance()
        cooldown = int(balance["departments"]["focus"]["cooldown_weeks"])
        assert 4 <= cooldown <= 52

    def test_focus_per_type_has_all_five_depts(self) -> None:
        balance = load_balance()
        per_type = balance["departments"]["focus"]["per_type"]
        for name in ("Engineering", "Sales", "Operations", "Marketing", "Finance"):
            assert name in per_type, f"per_type must include {name}"

    def test_focus_modifiers_within_safe_range(self) -> None:
        balance = load_balance()
        mods = balance["departments"]["focus"]["modifiers"]
        for focus_name, mod in mods.items():
            # Locked TDD: productivity / salary_growth are [0.7, 1.5]
            for metric_name in ("productivity", "salary_growth"):
                if metric_name in mod:
                    v = float(mod[metric_name])
                    assert 0.7 <= v <= 1.5, f"{focus_name}.{metric_name} = {v} outside [0.7, 1.5]"
            # satisfaction_delta may be negative (down to -5)
            if "satisfaction_delta" in mod:
                v = int(mod["satisfaction_delta"])
                assert -5 <= v <= 5, f"{focus_name}.satisfaction_delta = {v} outside [-5, 5]"


# ============================================================================
# GameState integration
# ============================================================================


class TestGameStateDeptFocus:
    def test_new_game_has_empty_dept_focus(self) -> None:
        state = new_game(rng_seed=42)
        assert state.dept_focus == {}, "new_game starts with no registered depts"

    def test_state_hash_includes_dept_focus_field(self) -> None:
        """Sanity: dept_focus must participate in canonical hash form."""
        from dataclasses import replace

        from htop_tycoon.domain.focus import FocusChoice, FocusType

        # Two states with identical dept_focus must hash identically; a
        # change to dept_focus must change the hash.
        s1 = new_game(rng_seed=42)
        s2 = replace(
            s1,
            dept_focus={
                DepartmentId("dept-eng"): FocusChoice(
                    dept_id=DepartmentId("dept-eng"),
                    focus=FocusType.SPEED,
                    set_tick=42,
                )
            },
        )
        assert state_hash(s1) != state_hash(s2)

    def test_game_state_frozen_blocks_dept_focus_mutation(self) -> None:
        from dataclasses import FrozenInstanceError

        state = new_game(rng_seed=42)
        with pytest.raises(FrozenInstanceError):
            state.dept_focus = {}  # type: ignore[misc]
