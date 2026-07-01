"""htop-tycoon v3.0 — daily game-development loop. Spec §2.2.

The ``advance_projects`` function ticks every in-progress ``GameProject`` by
one game-day, summing each assignee's per-axis skill contribution to drive
``progress_pct`` toward 100. At the 25/50/75% milestones an ``Event(kind=
'milestone')`` is emitted so the UI can prompt for the spec §2.2 step-4
"special task" bonus (Wave 4+).

Anti-pattern guards (per AGENTS.md §8):
  - No ``import random`` — GameRNG is the only randomness gateway.
  - No I/O, no clock access — pure values only.
  - Balance constants live in ``data/balance.yaml``; this module mirrors
    them as module-level constants with comments pointing to the YAML
    source (Wave 5+ data loader will replace the literals).
"""
from __future__ import annotations

import dataclasses

from htop_tycoon.domain import (
    Employee,
    Event,
    GameProject,
    GameState,
    ProjectId,
    QualityAxis,
)

# Spec §2.2 step 4: milestones at 25/50/75 percent. Mirrored from
# balance.yaml (no dedicated key yet; the Wave 5 data loader will source
# these at runtime once milestone bonuses are introduced).
_MILESTONE_PCTS: tuple[float, ...] = (25.0, 50.0, 75.0)

__all__ = ["advance_projects", "is_project_complete"]


def is_project_complete(project: GameProject) -> bool:
    """Return ``True`` if the project's ``progress_pct`` has reached 100.

    Thin wrapper around ``GameProject.is_complete`` for callers that prefer
    a free function. Spec §2.2 step 5.
    """
    return project.is_complete


def _contributors_for(
    state: GameState, project: GameProject
) -> list[Employee]:
    """Resolve ``project.assignees`` to live ``Employee`` records.

    Unknown IDs are silently skipped (defensive: an ASSIGN action could
    be in-flight or undone across save/load). Returns an empty list when
    the project has no assignees — the "zombie game" condition from
    spec §1.3 (balance.yaml::zombie.stuck_threshold_days = 7).
    """
    assignee_ids = set(project.assignees)
    return [e for e in state.employees if e.id in assignee_ids]


def _daily_contribution(contributors: list[Employee]) -> float:
    """Sum per-employee contributions for the FUN axis.

    Spec §2.2 step 3: ``progress += sum(employee.skill * dept_bonus)``.
    Wave 3-B ships a simple single-axis sum (FUN only) — programmer/hacker
    already carry a baked-in 2× weight via ``skill_per_axis`` (see
    ``domain/enums._JOB_QUALITY_CONTRIBUTIONS``) so the FUN axis naturally
    dominates the FUN-focused projects that programmers work on. Other
    axes affect *quality* at scoring time (critic.py), not progress.

    Returns 0.0 for an empty contributor list (zombie game).
    """
    if not contributors:
        return 0.0
    return sum(e.skill_per_axis.get(QualityAxis.FUN, 0.0) for e in contributors)


def _milestone_events(
    project: GameProject, prev_pct: float, new_pct: float, day: int
) -> list[Event]:
    """Emit a ``milestone`` event for each spec §2.2 step-4 threshold crossed.

    A threshold is "crossed" when ``prev_pct < milestone <= new_pct``. The
    strict-less-than on the left prevents re-emitting a milestone that was
    crossed in a previous tick; the less-than-or-equal on the right covers
    both exact arrival and skip-over (e.g. 20% → 30% still emits the 25%
    event).
    """
    events: list[Event] = []
    for milestone in _MILESTONE_PCTS:
        if prev_pct < milestone <= new_pct:
            events.append(
                Event(
                    kind="milestone",
                    day=day,
                    payload={
                        "project_id": project.id,
                        "milestone_pct": milestone,
                    },
                )
            )
    return events


def advance_projects(state: GameState) -> tuple[GameState, list[Event]]:
    """Advance every in-progress project by one game-day. Spec §2.2.

    For each non-complete project:

      1. Resolve assignees → live ``Employee`` records.
      2. Sum per-assignee contributions (``skill_per_axis[FUN]``).
      3. ``progress_pct += daily_contribution`` (clamped at 100).
      4. Emit ``milestone`` events for any 25/50/75% thresholds crossed.

    Completed projects (progress_pct >= 100) are passed through unchanged;
    they become eligible for the sales-release action in Wave 3-C.

    Pure function (spec §5.3): same ``state`` input yields the same
    ``(new_state, events)`` pair. Returns ``(state, [])`` for a state
    with no active projects.
    """
    events: list[Event] = []
    new_projects: list[GameProject] = []

    for project in state.projects:
        if project.is_complete:
            new_projects.append(project)
            continue

        contributors = _contributors_for(state, project)
        daily = _daily_contribution(contributors)
        prev_pct = project.progress_pct
        # Wave 3-B: single-axis sum. Wave 4 may weight by dept bonus.
        new_pct = min(100.0, prev_pct + daily)
        events.extend(_milestone_events(project, prev_pct, new_pct, state.day))
        new_projects.append(dataclasses.replace(project, progress_pct=new_pct))

    return state.replace(projects=tuple(new_projects)), events


def project_ids_for(state: GameState) -> tuple[ProjectId, ...]:
    """Helper: list every project ID. Reserved for Wave 4+ UI integration."""
    return tuple(p.id for p in state.projects)
