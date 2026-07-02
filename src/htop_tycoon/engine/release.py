"""Release logic — explicitly launch a shipped project on a target console.

Phase 2J. Differs from engine/tick._ship_projects (which auto-ships any
project reaching progress=100) — release_project is the explicit
'pick a console + launch' action a player takes from the release screen.
"""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Console,
    GameProject,
    ProjectId,
)
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine.market import MarketState
from htop_tycoon.engine.sales import compute_sales_revenue, compute_units_sold


def release_project(
    state: CompanyState,
    project_id: ProjectId,
    target_console: Console,
    market: MarketState,
    rng: GameRng,
) -> CompanyState:
    """Launch a shipped project on a target console.

    Computes revenue + units_sold + fans, deducts from project quality
    if quality < threshold (rare), removes the project from active
    development (it ships).
    """
    project = state.projects.get(project_id)
    if project is None:
        raise ValueError(f"project {project_id} not found")
    if not project.is_shipped:
        raise ValueError(f"project {project_id} is not shipped yet")

    units = compute_units_sold(project, market, rng)
    revenue = compute_sales_revenue(project, market, rng)
    fans = project.quality.sum() // 100

    new_state = state.adjust_cash(revenue).add_fans(fans)
    from dataclasses import replace

    if target_console is not None:
        new_project = replace(project, units_sold=units, console=target_console)
    else:
        new_project = replace(project, units_sold=units)

    if new_project.units_sold >= 1_000_000:
        new_state = new_state.increment_mega_hits()

    new_projects = dict(new_state.projects)
    new_projects[project_id] = new_project
    from dataclasses import replace as _replace

    return _replace(new_state, projects=new_projects)


def releaseable_projects(state: CompanyState) -> list[GameProject]:
    """Projects ready to release (progress >= 100, not yet released on console)."""
    return [p for p in state.projects.values() if p.is_shipped]
