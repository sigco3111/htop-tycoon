"""game_dev — daily progress for in-development projects + batch advance."""

from __future__ import annotations

from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.enums import Genre
from htop_tycoon.domain.ids import ProjectId
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.quality import QualityAxes
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.domain.state import CompanyState
from htop_tycoon.engine.productivity import compute_employee_productivity

BASE_PROGRESS_PER_DAY: int = 5
TEAM_SIZE_BONUS_CAP: int = 5
TEAM_SIZE_BONUS_PER: float = 0.10
QUALITY_UPGRADE_CHANCE_PERCENT: int = 5

GENRE_FACTOR: dict[Genre, float] = {
    Genre.ACTION: 1.2,
    Genre.RPG: 1.1,
    Genre.ADVENTURE: 1.0,
    Genre.SIMULATION: 1.0,
    Genre.PUZZLE: 0.9,
    Genre.STRATEGY: 0.9,
    Genre.SPORTS: 1.1,
    Genre.HORROR: 0.9,
    Genre.CASUAL: 1.0,
}


def _team_bonus(team_size: int) -> float:
    return 1.0 + TEAM_SIZE_BONUS_PER * min(team_size, TEAM_SIZE_BONUS_CAP)


def compute_daily_progress(
    project: GameProject, state: CompanyState, rng: GameRng
) -> int:
    """Integer delta for one day of development.

    Returns 0 if no lead, lead absent from state, or project shipped.
    """
    if project.is_shipped:
        return 0
    if project.lead_id is None:
        return 0
    lead: Employee | None = state.employees.get(project.lead_id)
    if lead is None:
        return 0

    lead_productivity = compute_employee_productivity(lead, rng)
    if lead_productivity <= 0:
        return 0

    team_bonus = _team_bonus(len(project.team_ids))
    genre_factor = GENRE_FACTOR[project.genre]
    raw = BASE_PROGRESS_PER_DAY * lead_productivity * team_bonus * genre_factor
    return max(1, int(round(raw)))


def _maybe_upgrade_quality(quality: QualityAxes, rng: GameRng) -> QualityAxes:
    """5% chance per tick to +1 a random axis. Returns new QualityAxes."""
    if rng.int_range(1, 100) > QUALITY_UPGRADE_CHANCE_PERCENT:
        return quality
    axis_index = rng.int_range(0, 3)  # 0..3 inclusive for 4 axes
    axes = [quality.fun, quality.graphics, quality.sound, quality.originality]
    axes[axis_index] = min(100, axes[axis_index] + 1)
    return QualityAxes(*axes)


def advance_projects(state: CompanyState, rng: GameRng) -> CompanyState:
    """Advance every project by one day; return new state."""
    new_projects: dict[ProjectId, GameProject] = {}
    for pid, project in state.projects.items():
        delta = compute_daily_progress(project, state, rng)
        if delta > 0:
            advanced = project.advance(delta)
        else:
            advanced = project
        new_quality = _maybe_upgrade_quality(advanced.quality, rng)
        if new_quality is not advanced.quality:
            advanced = GameProject(
                id=advanced.id,
                title=advanced.title,
                genre=advanced.genre,
                platform=advanced.platform,
                console=advanced.console,
                progress=advanced.progress,
                quality=new_quality,
                days_in_dev=advanced.days_in_dev,
                lead_id=advanced.lead_id,
                team_ids=advanced.team_ids,
            )
        new_projects[pid] = advanced
    from dataclasses import replace

    return replace(state, projects=new_projects)
