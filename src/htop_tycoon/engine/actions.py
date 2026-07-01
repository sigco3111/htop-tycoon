"""htop-tycoon v3.0 — 9 pure player actions. Spec §3.2.1 + §6.

Each action is a pure function:
    ``action(state, rng, **params) -> tuple[GameState, list[Event]]``

Errors return ``(state, [failure_event])`` (spec §6 contract):
- hire with insufficient budget     -> HireFailedEvent (cash unchanged)
- start_game with active project    -> StartGameFailedEvent
- start_game with no dept unlocked  -> StartGameFailedEvent (Wave 4+)
- assign/change_job on missing id   -> ActionFailedEvent

Determinism: all randomness via the injected ``GameRNG`` argument.
No bare ``import random`` (enforced by tests/test_rng.py).

Wave 3 scope:
- Manual play only. Strategy Manager integration is Wave 4.
- ``assign`` does NOT validate dept-contributes-to-genre/theme yet;
  Wave 4+ will tighten that. ``start_game`` checks max 1 active project
  per spec §1.3 (single-project-at-a-time is the scope cap for v3.0).
- Constants below are hardcoded mirrors of ``data/balance.yaml`` until
  the Wave 5 data loader lands.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from htop_tycoon.domain import (
    Department,
    Employee,
    Event,
    EventKind,
    GameProject,
    GameState,
    GenreId,
    JobType,
    PlatformId,
    ThemeId,
)
from htop_tycoon.domain.employee import (
    _salary_for,
    _skill_per_axis_for,
)
from htop_tycoon.domain.ids import (
    new_employee_id,
    new_project_id,
)
from htop_tycoon.engine.rng import GameRNG

# --------------------------------------------------------------------------
# Balance constants (hardcoded mirror of data/balance.yaml for Wave 3;
# data loader in Wave 5+ will replace these at runtime).
# --------------------------------------------------------------------------
HIRE_COST: int = 1000                    # balance.yaml costs.hire_cost
FIRE_SEVERANCE: int = 500                # balance.yaml costs.fire_severance
TRAIN_COST_PER_LEVEL: int = 800          # balance.yaml costs.train_cost_per_level
CONSOLE_LICENSE_FEE: int = 15000         # balance.yaml costs.console_license_fee
JOB_CHANGE_MULTIPLIER: float = 1.2       # balance.yaml employee.job_change_multiplier
MAX_LEVEL: int = 5                       # balance.yaml employee.max_level

# Spec §6: "Strategy decision infinite loop -> capped at
# balance.ai.max_actions_per_day (default 10)."
MAX_ACTIONS_PER_DAY: int = 10            # balance.yaml ai.max_actions_per_day


# --------------------------------------------------------------------------
# Deterministic Korean name pool — only GameRNG.choice() touches it.
# --------------------------------------------------------------------------
_KOREAN_SURNAMES: tuple[str, ...] = (
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
    "한", "오", "서", "신", "권", "황", "안", "송", "유", "홍",
)
_KOREAN_GIVEN_NAMES: tuple[str, ...] = (
    "민준", "서준", "도윤", "예준", "시우", "주원", "하준", "지호", "지후", "서연",
    "서윤", "지우", "서현", "민서", "하은", "하윤", "지유", "윤서", "지민", "채영",
)


def _random_korean_name(rng: GameRNG) -> str:
    """Pick a deterministic Korean name from the fixed surname × given list."""
    return f"{rng.choice(_KOREAN_SURNAMES)}{rng.choice(_KOREAN_GIVEN_NAMES)}"


# --------------------------------------------------------------------------
# Helpers (lookup + event construction)
# --------------------------------------------------------------------------
def _find_employee(state: GameState, employee_id: str) -> Employee | None:
    """Locate an employee by id; O(n) over state.employees."""
    for e in state.employees:
        if e.id == employee_id:
            return e
    return None


def _find_project(state: GameState, project_id: str) -> GameProject | None:
    """Locate a project by id; O(n) over state.projects."""
    for p in state.projects:
        if p.id == project_id:
            return p
    return None


def _payload(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Identity wrapper used to lock the static type as Mapping[str, Any].

    mypy strict rejects ``dict[str, str]`` being passed where
    ``Mapping[str, Any]`` is expected (dict invariance in V). This helper
    accepts any Mapping and surfaces the widened type without an ignore.
    """
    return data


def _ok_event(
    state: GameState,
    kind: EventKind,
    payload: Mapping[str, Any] | None = None,
) -> Event:
    """Build a success event with the current day."""
    return Event(kind=kind, day=state.day, payload=_payload(dict(payload) if payload else {}))


def _fail_event(
    state: GameState,
    kind: EventKind,
    reason: str,
    **extra: Any,
) -> Event:
    """Build a failure event with ``status='failed'`` and a structured reason."""
    body: dict[str, Any] = {"status": "failed", "reason": reason}
    body.update(extra)
    return Event(kind=kind, day=state.day, payload=_payload(body))


# ==========================================================================
# 9 actions per spec §3.2.1
# ==========================================================================
def hire(
    state: GameState,
    rng: GameRNG,
    *,
    dept: Department,
    job: JobType,
) -> tuple[GameState, list[Event]]:
    """Spec §3.2.1 + §6: insufficient cash -> returns (state, [HireFailedEvent])."""
    if state.cash < HIRE_COST:
        return state, [_fail_event(
            state, "hire", "insufficient_cash",
            required=HIRE_COST, available=state.cash,
        )]
    new_emp = Employee(
        id=new_employee_id(),
        name=_random_korean_name(rng),
        dept=dept,
        job=job,
        level=1,
    )
    return (
        state.replace(
            cash=state.cash - HIRE_COST,
            employees=state.employees + (new_emp,),
        ),
        [_ok_event(state, "hire", {
            "status": "ok",
            "employee_id": new_emp.id,
            "dept": dept.name,
            "job": job.name,
        })],
    )


def fire(
    state: GameState,
    rng: GameRNG,
    *,
    employee_id: str,
    reason: str,
) -> tuple[GameState, list[Event]]:
    """Spec §3.2.1: remove employee + pay severance."""
    emp = _find_employee(state, employee_id)
    if emp is None:
        return state, [_fail_event(
            state, "fire", "employee_not_found", employee_id=employee_id,
        )]
    return (
        state.replace(
            cash=state.cash - FIRE_SEVERANCE,
            employees=tuple(e for e in state.employees if e.id != employee_id),
        ),
        [_ok_event(state, "fire", {
            "status": "ok",
            "employee_id": employee_id,
            "reason": reason,
        })],
    )


def train(
    state: GameState,
    rng: GameRNG,
    *,
    employee_id: str,
    target_level: int,
) -> tuple[GameState, list[Event]]:
    """Spec §3.2.1: pay TRAIN_COST_PER_LEVEL * delta, raise to target level."""
    emp = _find_employee(state, employee_id)
    if emp is None:
        return state, [_fail_event(
            state, "train", "employee_not_found", employee_id=employee_id,
        )]
    if target_level < emp.level or target_level > MAX_LEVEL:
        return state, [_fail_event(
            state, "train", "target_out_of_range",
            current=emp.level, target=target_level, max=MAX_LEVEL,
        )]
    delta = target_level - emp.level
    cost = delta * TRAIN_COST_PER_LEVEL
    if state.cash < cost:
        return state, [_fail_event(
            state, "train", "insufficient_cash",
            required=cost, available=state.cash,
        )]
    # Apply level-ups one step at a time so __post_init__ recomputes
    # salary/skill consistently at each step.
    new_emp = emp
    for _ in range(delta):
        new_emp = new_emp.apply_level_up()
    return (
        state.replace(
            cash=state.cash - cost,
            employees=tuple(
                e if e.id != employee_id else new_emp for e in state.employees
            ),
        ),
        [_ok_event(state, "train", {
            "status": "ok",
            "employee_id": employee_id,
            "from_level": emp.level,
            "to_level": target_level,
            "cost": cost,
        })],
    )


def promote(
    state: GameState,
    rng: GameRNG,
    *,
    employee_id: str,
) -> tuple[GameState, list[Event]]:
    """Spec §4.1 key F7: train employee to next level (1 step). Delegates to train()."""
    emp = _find_employee(state, employee_id)
    if emp is None:
        return state, [_fail_event(
            state, "promote", "employee_not_found", employee_id=employee_id,
        )]
    return train(state, rng, employee_id=employee_id, target_level=emp.level + 1)


def demote(
    state: GameState,
    rng: GameRNG,
    *,
    employee_id: str,
) -> tuple[GameState, list[Event]]:
    """Spec §4.1 key F8: reduce level by 1 step. No cost. Refreshes salary + skills."""
    emp = _find_employee(state, employee_id)
    if emp is None:
        return state, [_fail_event(
            state, "demote", "employee_not_found", employee_id=employee_id,
        )]
    if emp.level <= 1:
        return state, [_fail_event(
            state, "demote", "already_at_minimum", current=emp.level,
        )]
    new_level = emp.level - 1
    # Employee has no apply_level_down helper. Recompute derived fields via
    # the module-level domain helpers (also used by Employee.__post_init__).
    new_emp = dataclasses.replace(
        emp,
        level=new_level,
        salary_daily=_salary_for(emp.job, new_level),
        skill_per_axis=_skill_per_axis_for(emp.job, new_level),
    )
    return (
        state.replace(
            employees=tuple(
                e if e.id != employee_id else new_emp for e in state.employees
            ),
        ),
        [_ok_event(state, "demote", {
            "status": "ok",
            "employee_id": employee_id,
            "from_level": emp.level,
            "to_level": new_level,
        })],
    )


def change_job(
    state: GameState,
    rng: GameRNG,
    *,
    employee_id: str,
    new_job: JobType,
) -> tuple[GameState, list[Event]]:
    """Spec §2.5: change job multiplies salary by JOB_CHANGE_MULTIPLIER (1.2)."""
    emp = _find_employee(state, employee_id)
    if emp is None:
        return state, [_fail_event(
            state, "change_job", "employee_not_found", employee_id=employee_id,
        )]
    if new_job is emp.job:
        return state, [_fail_event(
            state, "change_job", "same_job", current=new_job.name,
        )]
    new_emp = emp.change_job(new_job, JOB_CHANGE_MULTIPLIER)
    return (
        state.replace(
            employees=tuple(
                e if e.id != employee_id else new_emp for e in state.employees
            ),
        ),
        [_ok_event(state, "change_job", {
            "status": "ok",
            "employee_id": employee_id,
            "from_job": emp.job.name,
            "to_job": new_job.name,
        })],
    )


def start_game(
    state: GameState,
    rng: GameRNG,
    *,
    genre_id: GenreId,
    theme_id: ThemeId,
    platform_id: PlatformId,
) -> tuple[GameState, list[Event]]:
    """Spec §3.2.1 + §1.3: at most 1 active project. Fails if busy.

    Wave 3 stub: the project is created with no assignees and zero progress.
    ``game_dev.advance_projects`` (Wave 3-B) will fill in the rest.
    """
    active = state.active_projects()
    if active:
        return state, [_fail_event(
            state, "start_game", "active_project_exists",
            active_project_id=active[0].id,
        )]
    new_proj = GameProject(
        id=new_project_id(),
        name=f"{genre_id} {theme_id} Game",
        genre_id=genre_id,
        theme_id=theme_id,
        platform_id=platform_id,
        progress_pct=0.0,
        assignees=(),
        started_day=state.day,
    )
    return (
        state.replace(projects=state.projects + (new_proj,)),
        [_ok_event(state, "start_game", {
            "status": "ok",
            "project_id": new_proj.id,
            "genre_id": genre_id,
            "theme_id": theme_id,
            "platform_id": platform_id,
        })],
    )


def assign(
    state: GameState,
    rng: GameRNG,
    *,
    employee_id: str,
    project_id: str,
) -> tuple[GameState, list[Event]]:
    """Assign an employee to a project (append to ``project.assignees``).

    Wave 3 stub: does NOT yet validate that ``employee.dept`` contributes to
    the project's genre/theme combination (spec §2.1 — full per-axis-weight
    validation lands with the game_dev module in Wave 3-B+).
    """
    emp = _find_employee(state, employee_id)
    if emp is None:
        return state, [_fail_event(
            state, "assign", "employee_not_found", employee_id=employee_id,
        )]
    proj = _find_project(state, project_id)
    if proj is None:
        return state, [_fail_event(
            state, "assign", "project_not_found", project_id=project_id,
        )]
    if employee_id in proj.assignees:
        return state, [_fail_event(
            state, "assign", "already_assigned",
            employee_id=employee_id, project_id=project_id,
        )]
    # GameProject.assignees is tuple[EmployeeId, ...]; the parameter is
    # typed str for the public API. Runtime they are the same NewType.
    # Build the new assignees tuple via an explicit list-then-tuple cast.
    # GameProject.assignees is tuple[EmployeeId, ...]; tuple concat with a
    # plain str produces tuple[EmployeeId | str, ...] which mypy rejects on
    # invariance. The cast wraps the result back into the same length tuple.
    appended: tuple[Any, ...] = tuple(
        a for a in (*proj.assignees, employee_id)
    )
    new_proj = dataclasses.replace(
        proj,
        assignees=appended,
    )
    return (
        state.replace(
            projects=tuple(
                p if p.id != project_id else new_proj for p in state.projects
            ),
        ),
        [_ok_event(state, "assign", {
            "status": "ok",
            "employee_id": employee_id,
            "project_id": project_id,
        })],
    )


def nothing(
    state: GameState,
    rng: GameRNG,
) -> tuple[GameState, list[Event]]:
    """Spec §3.2.1: no-op marker. Returns ``(state, [])``."""
    return state, []


__all__ = [
    "CONSOLE_LICENSE_FEE",
    "FIRE_SEVERANCE",
    "HIRE_COST",
    "JOB_CHANGE_MULTIPLIER",
    "MAX_ACTIONS_PER_DAY",
    "MAX_LEVEL",
    "TRAIN_COST_PER_LEVEL",
    "assign",
    "change_job",
    "demote",
    "fire",
    "hire",
    "nothing",
    "promote",
    "start_game",
    "train",
]
