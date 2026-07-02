"""htop-tycoon v3.0 — engine.critic coverage tests. Spec §2.2 step 6.

Targets ``engine/critic.py`` (currently 0% covered) to push above 80%.

Verifies:
- ``score_project`` returns a dict for every QualityAxis, with values
  in [0, 10] (clamped), seeded by the injected GameRNG.
- Unknown ``project_id`` raises ``KeyError`` (engine §5.3 invariant).
- ``hall_of_fame_eligible`` boundary semantics (default 8.0 / 5),
  and the custom threshold overload.
"""
from __future__ import annotations

import pytest

from htop_tycoon.domain import (
    GameProject,
    GameState,
    GenreId,
    Platform,
    PlatformId,
    ProjectId,
    QualityAxis,
    ThemeId,
)
from htop_tycoon.engine.critic import hall_of_fame_eligible, score_project
from htop_tycoon.engine.rng import GameRNG

# --- helpers --------------------------------------------------------------


def _make_project(pid: str, base_avg: float) -> GameProject:
    """Build a project with all four axes at ``base_avg``."""
    return GameProject(
        id=ProjectId(pid),
        name=pid,
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=100.0,
        released_day=1,
        quality_axes={axis: base_avg for axis in QualityAxis},
    )


def _state_with(*projects: GameProject) -> GameState:
    return GameState(rng_seed=42, projects=projects)


# --- score_project: structural contract ---------------------------------


def test_score_project_returns_dict_for_all_axes() -> None:
    """All four QualityAxis members must appear in the returned dict."""
    state = _state_with(_make_project("p1", 5.0))
    scores = score_project(state, ProjectId("p1"), GameRNG(42))
    assert set(scores.keys()) == set(QualityAxis)
    for axis in QualityAxis:
        assert isinstance(scores[axis], float)


def test_score_project_axis_value_base_plus_perturbation() -> None:
    """Each axis value lies within ±1.0 of the base value (before clamp)."""
    state = _state_with(_make_project("p1", 6.0))
    scores = score_project(state, ProjectId("p1"), GameRNG(42))
    for axis in QualityAxis:
        # base = 6.0, perturbation ∈ [-1.0, 1.0) -> result in [5.0, 7.0]
        assert 5.0 <= scores[axis] <= 7.0


# --- score_project: clamping --------------------------------------------


def test_score_project_clamps_to_zero_when_negative() -> None:
    """A base of 0.0 with -1.0 perturbation clamps to 0.0 (not negative)."""
    # Use a fresh RNG with the worst case: rng.uniform returns the low edge
    # -1.0 only if it happens to; we force the result by stress-testing.
    # We instead craft a deterministic check: when base == 0 the score
    # must always be >= 0 (clamped) regardless of RNG seed.
    state = _state_with(_make_project("p1", 0.0))
    for seed in range(50):
        scores = score_project(state, ProjectId("p1"), GameRNG(seed))
        for axis in QualityAxis:
            assert 0.0 <= scores[axis] <= 1.0


def test_score_project_clamps_to_ten_when_above() -> None:
    """A base of 10.0 with +1.0 perturbation clamps to 10.0."""
    state = _state_with(_make_project("p1", 10.0))
    for seed in range(50):
        scores = score_project(state, ProjectId("p1"), GameRNG(seed))
        for axis in QualityAxis:
            assert 9.0 <= scores[axis] <= 10.0


def test_score_project_all_scores_in_valid_band() -> None:
    """All scores always lie in [0.0, 10.0] (the critic-score band)."""
    state = _state_with(_make_project("p1", 7.0))
    for seed in range(20):
        scores = score_project(state, ProjectId("p1"), GameRNG(seed))
        for axis in QualityAxis:
            assert 0.0 <= scores[axis] <= 10.0


# --- score_project: determinism + error path ----------------------------


def test_score_project_deterministic_same_seed() -> None:
    """Two GameRNG instances with the same seed produce identical scores."""
    state = _state_with(_make_project("p1", 5.0))
    scores_a = score_project(state, ProjectId("p1"), GameRNG(99))
    scores_b = score_project(state, ProjectId("p1"), GameRNG(99))
    assert scores_a == scores_b


def test_score_project_unknown_id_raises_key_error() -> None:
    """Unknown project_id -> KeyError (engine §5.3: never silent lookup failure)."""
    state = _state_with(_make_project("p1", 5.0))
    with pytest.raises(KeyError):
        score_project(state, ProjectId("missing"), GameRNG(42))


# --- hall_of_fame_eligible: count + threshold ---------------------------


def test_hall_of_fame_eligible_zero_released() -> None:
    """No released projects -> False."""
    state = _state_with()
    assert hall_of_fame_eligible(state) is False


def test_hall_of_fame_eligible_four_below_threshold() -> None:
    """4 released, each at avg 9.0 -> False (need 5)."""
    projects = tuple(_make_project(f"p{i}", 9.0) for i in range(4))
    state = _state_with(*projects)
    assert hall_of_fame_eligible(state) is False


def test_hall_of_fame_eligible_five_at_threshold() -> None:
    """5 released at avg 8.0 (boundary inclusive) -> True."""
    projects = tuple(_make_project(f"p{i}", 8.0) for i in range(5))
    state = _state_with(*projects)
    assert hall_of_fame_eligible(state) is True


def test_hall_of_fame_eligible_six_above() -> None:
    """6 released at avg 9.0 -> True."""
    projects = tuple(_make_project(f"p{i}", 9.0) for i in range(6))
    state = _state_with(*projects)
    assert hall_of_fame_eligible(state) is True


def test_hall_of_fame_eligible_one_below_threshold_excluded() -> None:
    """5 released but one below 8.0 -> False (only 4 qualify)."""
    projects = (
        tuple(_make_project(f"p{i}", 9.0) for i in range(4))
        + (_make_project("p4", 7.5),)  # one short
    )
    state = _state_with(*projects)
    assert hall_of_fame_eligible(state) is False


def test_hall_of_fame_eligible_unreleased_projects_ignored() -> None:
    """Unreleased projects (released_day=None) must not count toward HoF."""
    base = GameProject(
        id=ProjectId("unreleased"),
        name="In Progress",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=80.0,
        quality_axes={axis: 9.0 for axis in QualityAxis},
        released_day=None,
    )
    state = _state_with(*tuple(base for _ in range(10)))
    assert hall_of_fame_eligible(state) is False


# --- hall_of_fame_eligible: custom thresholds ---------------------------


def test_hall_of_fame_eligible_custom_min_score() -> None:
    """Custom min_score=7.0 with avg 7.5 -> eligible if count >= 5."""
    projects = tuple(_make_project(f"p{i}", 7.5) for i in range(5))
    state = _state_with(*projects)
    # Default threshold (8.0) rejects; lowered to 7.0 accepts.
    assert hall_of_fame_eligible(state) is False
    assert hall_of_fame_eligible(state, min_score=7.0) is True


def test_hall_of_fame_eligible_custom_min_count() -> None:
    """Custom min_count=2 -> True with 2 eligible projects (default 5 fails)."""
    projects = tuple(_make_project(f"p{i}", 8.5) for i in range(2))
    state = _state_with(*projects)
    assert hall_of_fame_eligible(state) is False
    assert hall_of_fame_eligible(state, min_count=2) is True
