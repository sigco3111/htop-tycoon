"""htop-tycoon v3.0 — engine.award coverage tests. Spec §2.4.

Targets ``engine/award.py`` (currently 22% covered) to push above 80%.

Anti-pattern guards honored:
- Real ``GameState`` aggregates; no engine-internal mocking.
- GameRNG used where determinism matters; bare ``random.*`` not touched.
"""
from __future__ import annotations

import dataclasses

from htop_tycoon.domain import (
    DEFAULT_STARTING_CASH,
    GameProject,
    GameState,
    GenreId,
    Platform,
    PlatformId,
    ProjectId,
    QualityAxis,
    ThemeId,
)
from htop_tycoon.engine.award import run_game_show, run_year_end_ceremony

# --- helpers --------------------------------------------------------------


def _base_axes(avg: float) -> dict[QualityAxis, float]:
    """All four axes equal to ``avg`` so ``current_quality_avg == avg``."""
    return {axis: avg for axis in QualityAxis}


def _released(quality_avg: float, released_day: int = 10) -> GameProject:
    """Construct a completed+released project with the given average score."""
    return GameProject(
        id=ProjectId("p"),
        name="Test Project",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=100.0,
        quality_axes=_base_axes(quality_avg),
        released_day=released_day,
    )


def _state_with_released(*projects: GameProject, cash: int = DEFAULT_STARTING_CASH) -> GameState:
    """Build a GameState carrying only released projects."""
    return GameState(rng_seed=42, projects=projects, cash=cash)


# --- run_year_end_ceremony: empty / no released projects ----------------


def test_year_end_ceremony_no_released_projects_no_delta() -> None:
    """No released projects -> cash unchanged, no prize, no penalty."""
    state = GameState(rng_seed=42, projects=(), cash=10_000)
    new_state, events = run_year_end_ceremony(state)
    assert new_state.cash == 10_000
    assert events == []


# --- run_year_end_ceremony: eligibility ladder ---------------------------


def test_year_end_ceremony_one_eligible_first_prize() -> None:
    """1 eligible (avg >= 5.0) -> +200,000 only."""
    state = _state_with_released(_released(6.0), cash=10_000)
    new_state, events = run_year_end_ceremony(state)
    assert new_state.cash == 210_000
    assert events == []


def test_year_end_ceremony_two_eligible_first_and_second() -> None:
    """2 eligible -> +200,000 + 100,000."""
    state = _state_with_released(_released(7.0), _released(8.0), cash=0)
    new_state, _ = run_year_end_ceremony(state)
    assert new_state.cash == 300_000


def test_year_end_ceremony_three_eligible_full_prize_ladder() -> None:
    """3 eligible -> +200k +100k +50k = +350,000."""
    p1, p2, p3 = _released(5.0), _released(5.5), _released(6.0)
    state = _state_with_released(p1, p2, p3, cash=50_000)
    new_state, _ = run_year_end_ceremony(state)
    assert new_state.cash == 50_000 + 350_000


# --- run_year_end_ceremony: trash penalty --------------------------------


def test_year_end_ceremony_trash_penalty_applied() -> None:
    """A released project with avg < 4.0 -> -100,000."""
    state = _state_with_released(_released(2.0), cash=200_000)
    new_state, _ = run_year_end_ceremony(state)
    assert new_state.cash == 100_000


def test_year_end_ceremony_both_eligible_and_trash() -> None:
    """Eligible (+200k) + trash (-100k) net +100,000."""
    state = _state_with_released(_released(6.0), _released(1.0), cash=500_000)
    new_state, _ = run_year_end_ceremony(state)
    assert new_state.cash == 500_000 + 100_000


def test_year_end_ceremony_multiple_trash_penalty_applied_once() -> None:
    """Trash penalty is a single -100,000 regardless of how many trash games."""
    state = _state_with_released(_released(1.0), _released(2.0), cash=500_000)
    new_state, _ = run_year_end_ceremony(state)
    assert new_state.cash == 400_000


# --- run_year_end_ceremony: boundary semantics ---------------------------


def test_year_end_ceremony_eligibility_threshold_at_5() -> None:
    """Quality avg exactly 5.0 is ELIGIBLE (>=)."""
    state = _state_with_released(_released(5.0), cash=0)
    new_state, _ = run_year_end_ceremony(state)
    # eligible (>=5.0) -> +200k
    assert new_state.cash == 200_000


def test_year_end_ceremony_trash_threshold_at_4() -> None:
    """Quality avg exactly 4.0 is NOT trash (>=4.0 means >= 4.0 keeps clean)."""
    state = _state_with_released(_released(4.0), cash=100_000)
    new_state, _ = run_year_end_ceremony(state)
    # 4.0 is >=4.0 (trash is <4.0); not eligible either (>=5.0 needed).
    assert new_state.cash == 100_000


def test_year_end_ceremony_below_5_but_at_or_above_4_neutral() -> None:
    """Quality avg 4.5 is neither eligible nor trash -> no delta."""
    state = _state_with_released(_released(4.5), cash=100_000)
    new_state, _ = run_year_end_ceremony(state)
    assert new_state.cash == 100_000


# --- run_game_show -------------------------------------------------------


def test_game_show_insufficient_funds_no_op() -> None:
    """Cash below participation cost -> state unchanged."""
    state = GameState(rng_seed=42, cash=10_000, fans=1_000)
    new_state, events = run_game_show(state)
    assert new_state.cash == 10_000
    assert new_state.fans == 1_000
    assert events == []


def test_game_show_applies_50_percent_fan_boost() -> None:
    """Sufficient cash -> fans x 1.5, cash - 20,000."""
    state = GameState(rng_seed=42, cash=100_000, fans=1_000)
    new_state, events = run_game_show(state)
    assert new_state.cash == 80_000
    assert new_state.fans == 1_500
    assert events == []


def test_game_show_exact_funds_succeeds() -> None:
    """Cash == participation cost exactly -> succeeds (boundary)."""
    state = GameState(rng_seed=42, cash=20_000, fans=200)
    new_state, _ = run_game_show(state)
    assert new_state.cash == 0
    assert new_state.fans == 300  # 200 * 1.5


def test_game_show_fans_zero_remain_zero() -> None:
    """Edge: fans == 0 stays at 0 after boost (0 * 1.5 = 0)."""
    state = GameState(rng_seed=42, cash=100_000, fans=0)
    new_state, _ = run_game_show(state)
    assert new_state.fans == 0
    assert new_state.cash == 80_000


def test_game_show_does_not_mutate_input_state() -> None:
    """Pure: input state must be unchanged after call."""
    state = GameState(rng_seed=42, cash=100_000, fans=1_000)
    _ = run_game_show(state)
    assert state.cash == 100_000
    assert state.fans == 1_000


# --- released vs unreleased filter ---------------------------------------


def test_year_end_ceremony_unreleased_projects_ignored() -> None:
    """Unreleased projects (released_day=None) must not affect prizes/penalties."""
    active = GameProject(
        id=ProjectId("active"),
        name="In Progress",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=50.0,
        quality_axes=_base_axes(8.0),  # would be eligible if released
    )
    trash_unreleased = dataclasses.replace(active, quality_axes=_base_axes(1.0))
    state = GameState(rng_seed=42, projects=(active, trash_unreleased), cash=100_000)
    new_state, _ = run_year_end_ceremony(state)
    assert new_state.cash == 100_000
