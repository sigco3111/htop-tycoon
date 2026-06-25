"""Tests for T9: TickEngine + GameTime advance + RNG integration.

Locks the contract from .omo/plans/htop-tycoon.md line 319-328 (Wave 2 patch
corrects the original quarter formula which had a precedence bug):

Week/quarter/year advance formulas (LOCKED, corrected):

- ``new_week    = ((state.game_time.week - 1 + n_ticks) % 52) + 1``
- ``new_quarter = (new_week - 1) // 13 + 1``
- ``new_year    = state.game_time.year + (state.game_time.week - 1 + n_ticks) // 52``

Quarter mapping (always consistent — derived from new_week):
    weeks  1-13 → Q1
    weeks 14-26 → Q2
    weeks 27-39 → Q3
    weeks 40-52 → Q4

The corrected formula fixes a precedence bug in the original plan's quarter
formula ``((Q-1) + (week-1+n) // 13 % 4) + 1`` where ``52 // 13 % 4 == 0`` at
year-end, leaving Q unchanged when it should advance. See the Wave 2 patch
note in the plan.

Construction:
- ``TickEngine(seed)`` requires an integer seed; ``TickEngine()`` raises
  ``TypeError`` (no implicit RNG, no ``None``).
- The engine holds its own ``GameRNG`` instance; ``advance`` advances the RNG
  once per tick (so the same engine + same seed yields the same tick-counter
  advances deterministically).

State:
- ``advance`` returns a NEW ``GameState`` (``dataclasses.replace``); the input
  is untouched.
- ``advance(state, 0)`` returns the SAME state object (no-op).
- ``advance(state, -1)`` raises ``ValueError`` (n_ticks must be >= 0).

Frozen state-hash determinism:
- ``advance(new_game(seed=42), n_ticks=100)`` produces a frozen expected
  ``state_hash`` after 100 ticks; same input → same hash, every run.
"""

from __future__ import annotations

import dataclasses

import pytest

from htop_tycoon.domain.state import (
    GameTime,
    new_game,
)
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.tick import TickEngine

# Frozen expected SHA-256 hex digest of state_hash(advance(new_game(42), 100)).
# Captured AFTER the engine was implemented and verified to be stable across
# 3 consecutive runs on Python 3.12.10 / macOS aarch64. Locking this value
# guarantees that any change to the advance formulas, RNG interaction, or
# GameState field-set is caught by the determinism invariant test.
#
# Resulting state (advance(new_game(42), 100)):
#   tick=100, game_time.week=49, game_time.quarter=4, game_time.year=2,
#   rng_seed=42, all collections empty.
#
# DO NOT update without a plan change + a recorded rationale in
# .omo/evidence/task-9-htop-tycoon.txt.
FROZEN_HASH_AFTER_100_TICKS_SEED_42 = (
    "15b9c9973079b16bdaa45727e0acf751f754bd9cada53b876c563321d7f0a0ef"
)


# -- Construction ------------------------------------------------------------


class TestTickEngineConstruction:
    """TickEngine requires an integer seed; no implicit RNG."""

    def test_construct_with_seed_returns_engine(self) -> None:
        """Given: an integer seed
        When: TickEngine(seed) is constructed
        Then: a TickEngine instance is returned
        """
        engine = TickEngine(seed=42)
        assert isinstance(engine, TickEngine)

    def test_construct_with_positional_seed(self) -> None:
        """TickEngine(42) (positional) is supported."""
        engine = TickEngine(42)  # type: ignore[arg-type]
        assert isinstance(engine, TickEngine)

    def test_construct_without_seed_raises_type_error(self) -> None:
        """TickEngine() with no arguments must raise TypeError (seed is required)."""
        with pytest.raises(TypeError):
            TickEngine()  # type: ignore[call-arg]

    def test_construct_with_none_seed_raises_type_error(self) -> None:
        """TickEngine(seed=None) must raise TypeError (no implicit seed)."""
        with pytest.raises(TypeError):
            TickEngine(seed=None)  # type: ignore[arg-type]

    def test_engine_holds_internal_rng(self) -> None:
        """The engine holds a GameRNG instance (attribute: _rng)."""
        engine = TickEngine(seed=42)
        assert isinstance(engine._rng, GameRNG)


# -- n_ticks validation -----------------------------------------------------


class TestTickEngineAdvanceValidation:
    """advance() validates n_ticks; rejects negative, accepts zero."""

    def test_advance_zero_returns_same_state_object(self) -> None:
        """Given: a state and n_ticks=0
        When: advance(state, 0) is called
        Then: the SAME state object is returned (no-op, no replace needed)
        """
        engine = TickEngine(seed=42)
        state = new_game(42)
        result = engine.advance(state, 0)
        assert result is state

    def test_advance_default_n_is_one(self) -> None:
        """advance(state) defaults to n_ticks=1."""
        engine = TickEngine(seed=42)
        state = new_game(42)
        result = engine.advance(state)
        assert result.tick == 1

    def test_advance_negative_raises_value_error(self) -> None:
        """advance(state, -1) raises ValueError."""
        engine = TickEngine(seed=42)
        state = new_game(42)
        with pytest.raises(ValueError):
            engine.advance(state, -1)


# -- Locked formula: week/quarter/year arithmetic ---------------------------


class TestTickEngineWeekWrap:
    """Week-wrap formula: new_week = ((week-1 + n) % 52) + 1."""

    def test_advance_1_from_week_52_goes_to_week_1(self) -> None:
        """Given: state at week=52
        When: advance(state, 1)
        Then: new_week == 1 (week wrap)
        """
        engine = TickEngine(seed=1)
        state = dataclasses.replace(
            new_game(1), game_time=GameTime(year=2026, quarter=4, week=52)
        )
        result = engine.advance(state, 1)
        assert result.game_time.week == 1

    def test_advance_1_from_week_1_goes_to_week_2(self) -> None:
        """Sanity: no-wrap advance preserves year and quarter."""
        engine = TickEngine(seed=1)
        state = new_game(1)
        result = engine.advance(state, 1)
        assert result.game_time.week == 2
        assert result.game_time.quarter == 1
        assert result.game_time.year == 1

    def test_advance_52_weeks_returns_to_same_week(self) -> None:
        """52 ticks from week=1 → week=1, year+1."""
        engine = TickEngine(seed=1)
        state = new_game(1)
        result = engine.advance(state, 52)
        assert result.game_time.week == 1
        assert result.game_time.year == 2


# -- Locked boundary cases (Wave 2 patch) -----------------------------------


class TestTickEngineBoundaryEndOfYear:
    """(a) advance(1) from week=52 quarter=4 → week=1 quarter=1 year+1."""

    def test_end_of_year_rollover(self) -> None:
        """From end-of-year (week=52, Q4, Y=2026), advance 1 tick:
        new_week = 1, new_quarter = 1, new_year = 2027.
        """
        engine = TickEngine(seed=1)
        state = dataclasses.replace(
            new_game(1), game_time=GameTime(year=2026, quarter=4, week=52)
        )
        result = engine.advance(state, 1)
        assert result.game_time.week == 1
        assert result.game_time.quarter == 1
        assert result.game_time.year == 2027


class TestTickEngineBoundaryIntraYear:
    """(b) advance(13) from week=1 quarter=1 → week=14 quarter=2 year unchanged."""

    def test_intra_year_quarter_rollover(self) -> None:
        """From Q1 week=1, advance 13 ticks:
        new_week = 14, new_quarter = 2, new_year unchanged.
        """
        engine = TickEngine(seed=1)
        state = new_game(1)
        result = engine.advance(state, 13)
        assert result.game_time.week == 14
        assert result.game_time.quarter == 2
        assert result.game_time.year == 1


class TestTickEngineBoundaryFullYear:
    """(c) advance(52) from week=1 quarter=1 → week=1 quarter=1 year+1."""

    def test_full_year_rollover(self) -> None:
        """From Q1 week=1, advance 52 ticks (= 1 year):
        new_week = 1, new_quarter = 1, new_year = year + 1.
        """
        engine = TickEngine(seed=1)
        state = new_game(1)
        result = engine.advance(state, 52)
        assert result.game_time.week == 1
        assert result.game_time.quarter == 1
        assert result.game_time.year == 2


class TestTickEngineQuarterDerivation:
    """new_quarter = (new_week - 1) // 13 + 1. Verify each quarter boundary."""

    def test_q1_boundary_week_13_to_14(self) -> None:
        """From week=1 advance 12 → week=13 (still Q1); advance 13 → week=14 (Q2)."""
        engine = TickEngine(seed=1)
        state = new_game(1)
        at_13 = engine.advance(state, 12)
        assert at_13.game_time.week == 13
        assert at_13.game_time.quarter == 1
        at_14 = engine.advance(state, 13)
        assert at_14.game_time.week == 14
        assert at_14.game_time.quarter == 2

    def test_q2_to_q3_boundary(self) -> None:
        """From week=1 advance 26 → week=27 (Q3)."""
        engine = TickEngine(seed=1)
        state = new_game(1)
        result = engine.advance(state, 26)
        assert result.game_time.week == 27
        assert result.game_time.quarter == 3

    def test_q3_to_q4_boundary(self) -> None:
        """From week=1 advance 39 → week=40 (Q4)."""
        engine = TickEngine(seed=1)
        state = new_game(1)
        result = engine.advance(state, 39)
        assert result.game_time.week == 40
        assert result.game_time.quarter == 4

    def test_q4_end_to_q1_next_year(self) -> None:
        """From week=1 advance 52 → year+1, week=1, Q1."""
        engine = TickEngine(seed=1)
        state = new_game(1)
        result = engine.advance(state, 52)
        assert result.game_time.week == 1
        assert result.game_time.quarter == 1
        assert result.game_time.year == 2


class TestTickEngineYearFormula:
    """new_year = year + ((week-1 + n) // 52)."""

    def test_advance_1_from_week_52_q4_year_2026_increments_year(self) -> None:
        """From week=52 Q4 Y=2026, advance 1 → year=2027 (52//52=1)."""
        engine = TickEngine(seed=1)
        state = dataclasses.replace(
            new_game(1), game_time=GameTime(year=2026, quarter=4, week=52)
        )
        result = engine.advance(state, 1)
        assert result.game_time.year == 2027

    def test_advance_53_from_week_1_increments_year_by_1(self) -> None:
        """From week=1, advance 53 weeks → year+1 (53//52=1), week=2."""
        engine = TickEngine(seed=1)
        state = new_game(1)
        result = engine.advance(state, 53)
        assert result.game_time.year == 2
        assert result.game_time.week == 2  # ((1-1+53) % 52) + 1 = (53 % 52) + 1 = 2

    def test_advance_104_from_week_1_increments_year_by_2(self) -> None:
        """From week=1, advance 104 weeks → year+2."""
        engine = TickEngine(seed=1)
        state = new_game(1)
        result = engine.advance(state, 104)
        assert result.game_time.year == 3


# -- State immutability ----------------------------------------------------


class TestTickEngineImmutability:
    """advance() returns a new state via dataclasses.replace; input is untouched."""

    def test_advance_does_not_mutate_input_state(self) -> None:
        """advance(state, 1) returns a NEW state; the input is unchanged."""
        engine = TickEngine(seed=42)
        state = new_game(42)
        original_tick = state.tick
        original_week = state.game_time.week
        original_year = state.game_time.year
        _ = engine.advance(state, 1)
        assert state.tick == original_tick
        assert state.game_time.week == original_week
        assert state.game_time.year == original_year

    def test_advance_preserves_unrelated_fields(self) -> None:
        """Fields other than tick / game_time are preserved (e.g. company, rng_seed)."""
        engine = TickEngine(seed=42)
        state = new_game(42)
        result = engine.advance(state, 5)
        assert result.company == state.company
        assert result.rng_seed == state.rng_seed
        assert result.secret_investor_cleared == state.secret_investor_cleared
        assert result.version == state.version
        assert result.departments == state.departments
        assert result.employees == state.employees
        assert result.products == state.products
        assert result.competitors == state.competitors

    def test_advance_increments_tick_by_n(self) -> None:
        """result.tick == state.tick + n_ticks."""
        engine = TickEngine(seed=42)
        state = new_game(42)
        result = engine.advance(state, 7)
        assert result.tick == 7


# -- Sanity: formulas yield the values the plan locks ----------------------


class TestTickEngineFormulaSanity:
    """Sanity: formula computes the locked values for the headline inputs."""

    def test_advance_n_100_from_initial_state(self) -> None:
        """From new_game (week=1, q=1, year=1, tick=0), advance 100:
        week = ((0+100) % 52) + 1 = 49
        quarter = (49-1) // 13 + 1 = 4
        year = 1 + (100 // 52) = 2
        tick = 100
        """
        engine = TickEngine(seed=42)
        result = engine.advance(new_game(42), 100)
        assert result.game_time.week == 49
        assert result.game_time.quarter == 4
        assert result.game_time.year == 2
        assert result.tick == 100
