"""Tests for the T36 regime domain (RegimeType + RegimeModifiers +
TransitionWeights + RegimeCycleConfig + RegimeState) and its integration
into balance.yaml and GameState.

These tests follow the TDD contract: each scenario is a binary observable
against either a freshly constructed type or ``load_balance()`` /
``new_game(seed=42)``. The deterministic ``state_hash`` regression guard is
``tests/test_no_rebare_random.py`` + the v2 default hash re-tune in T46.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.regimes import RegimeState, RegimeType
from htop_tycoon.domain.state import (
    new_game,
    state_hash,
)
from htop_tycoon.engine.regimes import (
    RegimeCycleConfig,
    RegimeModifiers,
    TransitionWeights,
)

# ============================================================================
# RegimeType — 4-member enum locked to BOOM / NORMAL / RECESSION / CRISIS
# ============================================================================


class TestRegimeType:
    def test_has_exactly_four_members(self) -> None:
        assert len(RegimeType) == 4

    def test_member_names_are_locked(self) -> None:
        names = {member.name for member in RegimeType}
        assert names == {"BOOM", "NORMAL", "RECESSION", "CRISIS"}


# ============================================================================
# RegimeModifiers — 5 float fields, range [0.5, 2.0] / [0.0, 1.0]
# ============================================================================


class TestRegimeModifiers:
    def test_construction_with_balanced_values(self) -> None:
        mods = RegimeModifiers(
            revenue_multiplier=1.0,
            salary_growth_multiplier=1.0,
            competitor_aggression_baseline=0.4,
            event_probability_scale=1.0,
            cash_shock_probability=0.0,
        )
        assert mods.revenue_multiplier == 1.0
        assert mods.salary_growth_multiplier == 1.0
        assert mods.competitor_aggression_baseline == 0.4
        assert mods.event_probability_scale == 1.0
        assert mods.cash_shock_probability == 0.0

    def test_revenue_multiplier_below_floor_raises(self) -> None:
        with pytest.raises(ValueError):
            RegimeModifiers(
                revenue_multiplier=0.4,  # < 0.5
                salary_growth_multiplier=1.0,
                competitor_aggression_baseline=0.4,
                event_probability_scale=1.0,
                cash_shock_probability=0.0,
            )

    def test_revenue_multiplier_above_ceiling_raises(self) -> None:
        with pytest.raises(ValueError):
            RegimeModifiers(
                revenue_multiplier=2.5,  # > 2.0
                salary_growth_multiplier=1.0,
                competitor_aggression_baseline=0.4,
                event_probability_scale=1.0,
                cash_shock_probability=0.0,
            )

    def test_cash_shock_probability_above_one_raises(self) -> None:
        with pytest.raises(ValueError):
            RegimeModifiers(
                revenue_multiplier=1.0,
                salary_growth_multiplier=1.0,
                competitor_aggression_baseline=0.4,
                event_probability_scale=1.0,
                cash_shock_probability=1.5,  # > 1.0 always-True ceiling
            )

    def test_modifiers_is_frozen(self) -> None:
        mods = RegimeModifiers(
            revenue_multiplier=1.0,
            salary_growth_multiplier=1.0,
            competitor_aggression_baseline=0.4,
            event_probability_scale=1.0,
            cash_shock_probability=0.0,
        )
        with pytest.raises(FrozenInstanceError):
            mods.revenue_multiplier = 1.1  # type: ignore[misc]


# ============================================================================
# TransitionWeights — sum=1.0 invariant; string OR RegimeType keys
# ============================================================================


class TestTransitionWeights:
    def test_weights_summing_to_one_construct(self) -> None:
        weights = {"BOOM": 0.25, "NORMAL": 0.5, "RECESSION": 0.25}
        tw = TransitionWeights(weights=weights)
        assert sum(tw.weights.values()) == pytest.approx(1.0)

    def test_weights_not_summing_to_one_raises(self) -> None:
        with pytest.raises(ValueError, match="sum"):
            TransitionWeights(
                weights={"BOOM": 0.5, "NORMAL": 0.4, "RECESSION": 0.0}
            )

    def test_negative_weight_raises(self) -> None:
        with pytest.raises(ValueError):
            TransitionWeights(weights={"BOOM": 1.2, "NORMAL": -0.2})


# ============================================================================
# RegimeCycleConfig — composition with min/max weeks bounds
# ============================================================================


class TestRegimeCycleConfig:
    def test_construction_with_full_config(self) -> None:
        cfg = RegimeCycleConfig(
            type=RegimeType.BOOM,
            min_weeks_in_regime=40,
            max_weeks_in_regime=70,
            transition=TransitionWeights(
                weights={"NORMAL": 0.7, "RECESSION": 0.25, "CRISIS": 0.05}
            ),
            modifiers=RegimeModifiers(
                revenue_multiplier=1.3,
                salary_growth_multiplier=1.05,
                competitor_aggression_baseline=0.3,
                event_probability_scale=0.7,
                cash_shock_probability=0.0,
            ),
        )
        assert cfg.type is RegimeType.BOOM
        assert cfg.min_weeks_in_regime == 40
        assert cfg.max_weeks_in_regime == 70

    def test_min_weeks_above_max_raises(self) -> None:
        with pytest.raises(ValueError):
            RegimeCycleConfig(
                type=RegimeType.NORMAL,
                min_weeks_in_regime=100,
                max_weeks_in_regime=50,
                transition=TransitionWeights(weights={"BOOM": 1.0}),
                modifiers=RegimeModifiers(
                    revenue_multiplier=1.0,
                    salary_growth_multiplier=1.0,
                    competitor_aggression_baseline=0.4,
                    event_probability_scale=1.0,
                    cash_shock_probability=0.0,
                ),
            )


# ============================================================================
# RegimeState — frozen dataclass on GameState
# ============================================================================


class TestRegimeState:
    def test_can_construct_default_state(self) -> None:
        rs = RegimeState(current=RegimeType.NORMAL, weeks_in_regime=0, started_tick=0)
        assert rs.current is RegimeType.NORMAL
        assert rs.weeks_in_regime == 0
        assert rs.started_tick == 0

    def test_state_is_frozen(self) -> None:
        rs = RegimeState(current=RegimeType.NORMAL, weeks_in_regime=0, started_tick=0)
        with pytest.raises(FrozenInstanceError):
            rs.weeks_in_regime = 5  # type: ignore[misc]

    def test_negative_weeks_raises(self) -> None:
        with pytest.raises(ValueError):
            RegimeState(current=RegimeType.BOOM, weeks_in_regime=-1, started_tick=10)

    def test_negative_started_tick_raises(self) -> None:
        with pytest.raises(ValueError):
            RegimeState(current=RegimeType.BOOM, weeks_in_regime=0, started_tick=-1)


# ============================================================================
# balance.yaml integration
# ============================================================================


class TestRegimesInBalance:
    def test_load_balance_has_regimes_key(self) -> None:
        balance = load_balance()
        assert "regimes" in balance, "balance.yaml must have 'regimes' top-level key"

    def test_load_balance_has_cycles_for_each_regime(self) -> None:
        balance = load_balance()
        cycles = balance["regimes"]["cycles"]
        for name in ("BOOM", "NORMAL", "RECESSION", "CRISIS"):
            assert name in cycles, f"regimes.cycles.{name} missing"

    def test_boom_transition_normal_is_07(self) -> None:
        balance = load_balance()
        boom_trans = balance["regimes"]["cycles"]["BOOM"]["transition"]
        assert boom_trans["NORMAL"] == pytest.approx(0.7)

    def test_crisis_cash_shock_amount_is_positive_int(self) -> None:
        balance = load_balance()
        amount = balance["regimes"]["crisis_cash_shock_amount"]
        assert isinstance(amount, int)
        assert amount > 0

    def test_all_modifiers_within_bounds(self) -> None:
        balance = load_balance()
        cycles = balance["regimes"]["cycles"]
        for regime_name, cfg in cycles.items():
            m = cfg["modifiers"]
            assert 0.5 <= m["revenue_multiplier"] <= 2.0, (
                f"{regime_name}.revenue_multiplier {m['revenue_multiplier']} out of [0.5, 2.0]"
            )
            assert 0.5 <= m["salary_growth_multiplier"] <= 2.0
            assert 0.0 <= m["competitor_aggression_baseline"] <= 1.0
            assert 0.5 <= m["event_probability_scale"] <= 2.0
            assert 0.0 <= m["cash_shock_probability"] <= 1.0

    def test_each_regime_cycle_has_min_max_transition_modifiers(self) -> None:
        balance = load_balance()
        cycles = balance["regimes"]["cycles"]
        for name, cfg in cycles.items():
            assert "min_weeks" in cfg, f"cycles.{name}.min_weeks missing"
            assert "max_weeks" in cfg, f"cycles.{name}.max_weeks missing"
            assert cfg["min_weeks"] <= cfg["max_weeks"]
            assert "transition" in cfg
            assert "modifiers" in cfg


# ============================================================================
# GameState integration
# ============================================================================


class TestGameStateRegime:
    def test_new_game_has_default_regime_normal(self) -> None:
        state = new_game(rng_seed=42)
        assert isinstance(state.regime, RegimeState)
        assert state.regime.current is RegimeType.NORMAL
        assert state.regime.weeks_in_regime == 0
        assert state.regime.started_tick == 0

    def test_state_hash_is_deterministic_across_two_runs(self) -> None:
        h1 = state_hash(new_game(rng_seed=42))
        h2 = state_hash(new_game(rng_seed=42))
        assert h1 == h2, "state_hash must be deterministic for fixed seed"

    def test_state_hash_changes_when_regime_changes(self) -> None:
        # Sanity: regime must be part of canonical hash form.
        s_default = new_game(rng_seed=42)
        s_modified = replace(
            s_default,
            regime=RegimeState(
                current=RegimeType.BOOM, weeks_in_regime=1, started_tick=0
            ),
        )
        assert state_hash(s_default) != state_hash(s_modified)

    def test_game_state_frozen_blocks_regime_mutation(self) -> None:
        state = new_game(rng_seed=42)
        with pytest.raises(FrozenInstanceError):
            state.regime = RegimeState(  # type: ignore[misc]
                current=RegimeType.BOOM, weeks_in_regime=0, started_tick=0
            )


# ============================================================================
# Determinism invariant: the regimes module must not pull in stdlib random.
# (Bare-random detection in tests/test_no_bare_random.py enforces this at
# import time across the codebase; here we sanity-check the engine surface.)
# ============================================================================


class TestRegimesNoRandom:
    def test_engine_regimes_does_not_expose_random(self) -> None:
        import htop_tycoon.engine.regimes as regimes_module  # noqa: F401

        assert not hasattr(regimes_module, "random")
        assert not hasattr(regimes_module, "Random")
