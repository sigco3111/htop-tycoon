"""htop-tycoon v3.0 — 4-critic scoring. Spec §2.2 step 6.

Each completed game is scored by four critics, one per quality axis:

  - 전략 / Spec 평가  →  FUN
  - 그래픽 / 연출 평가 →  GRAPHICS
  - 음향 / 사운드 평가 →  SOUND
  - 독창성 / 신선함 평가 →  ORIGINALITY

The critic's raw score is the project's existing axis value (0-10) plus a
small ``GameRNG.uniform(-1, 1)`` perturbation, clamped to ``[0, 10]``.

The Hall-of-Fame check (``hall_of_fame_eligible``) implements spec §1.4
ending #4 — the "명예의 전당" soft ending, which fires when 5+ released
games have an average critic score of at least 8.0. The constants are
mirrored from ``data/balance.yaml::ending``; the Wave 5 data loader will
replace them with runtime lookups.

Anti-pattern guards (per AGENTS.md §8):
  - No ``import random`` — ``GameRNG`` is the only randomness gateway.
  - No I/O, no clock access — pure values only.
"""
from __future__ import annotations

from htop_tycoon.domain import (
    GameProject,
    GameState,
    ProjectId,
    QualityAxis,
)
from htop_tycoon.engine.rng import GameRNG

# Spec §2.2 step 6: critic scores are 0..10. The project already stores
# its base axis values in ``GameProject.quality_axes`` (0..10, see
# ``domain.project.GameProject.__post_init__``). We only apply a small
# perturbation per critic — the ±1.0 amplitude is a Wave 3-B simplification
# that gives the same game run-to-run variance without reshaping the
# quality economics.
_CRITIC_PERTURBATION_AMPLITUDE: float = 1.0
_CRITIC_SCORE_MIN: float = 0.0
_CRITIC_SCORE_MAX: float = 10.0

# Spec §1.4 ending #4 + balance.yaml::ending.
_HALL_OF_FAME_MIN_SCORE: float = 8.0   # balance.yaml ending.hall_of_fame_min_score
_HALL_OF_FAME_MIN_COUNT: int = 5       # balance.yaml ending.hall_of_fame_min_count

__all__ = ["score_project", "hall_of_fame_eligible"]


def _resolve_project(state: GameState, project_id: ProjectId) -> GameProject:
    """Return the project matching ``project_id``. Raises if missing.

    Spec §5.3: the engine never silently swallows lookup failures, so a
    missing ID is a programmer error. The wave-3 action layer validates
    IDs at the action boundary before calling critic functions.
    """
    for project in state.projects:
        if project.id == project_id:
            return project
    raise KeyError(f"project_id {project_id!r} not found in state.projects")


def score_project(
    state: GameState, project_id: ProjectId, rng: GameRNG
) -> dict[QualityAxis, float]:
    """Score a project on each of the 4 axes. Spec §2.2 step 6.

    Each axis's base value comes from ``GameProject.quality_axes``; the
    critic adds a uniform ``±_CRITIC_PERTURBATION_AMPLITUDE`` perturbation
    via the injected ``GameRNG`` and the result is clamped to
    ``[_CRITIC_SCORE_MIN, _CRITIC_SCORE_MAX]``. The 4 critics map 1:1 to
    the 4 ``QualityAxis`` members in enum order (deterministic).

    Determinism (spec §7.3): two ``GameRNG`` instances with the same seed
    produce identical perturbation sequences, so re-scoring is reproducible.

    Raises:
        KeyError: if ``project_id`` is not present in ``state.projects``.
    """
    project = _resolve_project(state, project_id)
    scored: dict[QualityAxis, float] = {}
    for axis in QualityAxis:
        base = project.quality_axes.get(axis, 0.0)
        perturbed = base + rng.uniform(
            -_CRITIC_PERTURBATION_AMPLITUDE, _CRITIC_PERTURBATION_AMPLITUDE
        )
        # Clamp to the valid 0..10 critic-score band.
        clamped = max(_CRITIC_SCORE_MIN, min(_CRITIC_SCORE_MAX, perturbed))
        scored[axis] = clamped
    return scored


def hall_of_fame_eligible(
    state: GameState,
    min_score: float = _HALL_OF_FAME_MIN_SCORE,
    min_count: int = _HALL_OF_FAME_MIN_COUNT,
) -> bool:
    """Return ``True`` when the Hall of Fame conditions are met. Spec §1.4.

    Counts released games (those with a non-``None`` ``released_day``) whose
    ``current_quality_avg`` is at least ``min_score``. The default thresholds
    (8.0, 5) mirror ``data/balance.yaml::ending``.

    Args:
        state: Current aggregate root.
        min_score: Critic-score threshold (default 8.0).
        min_count: Minimum number of qualifying games (default 5).

    Note:
        The function operates on the *project's* base quality axes, not on
        the per-critic perturbed scores — the perturbation is a one-shot
        affectation for the awards ceremony display, not a persistent
        attribute. Endings therefore use the deterministic stored values.
    """
    qualifying = [
        p for p in state.released_projects() if p.current_quality_avg >= min_score
    ]
    return len(qualifying) >= min_count
