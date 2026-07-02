"""Persistence layer: serialize CompanyState ↔ YAML.

Phase 2F. Pure functions, no I/O — callers (storage.py) handle file
operations. Brand types (EmployeeId, ProjectId, GameTitle) and
frozen value objects (Money, QualityAxes, Progress) are reconstructed
on load so the round-trip is type-faithful.
"""

from __future__ import annotations

from typing import Any

import yaml

from htop_tycoon.domain import (
    CompanyState,
    Console,
    Department,
    Employee,
    EmployeeId,
    GameProject,
    GameTitle,
    Genre,
    Job,
    Money,
    Platform,
    Progress,
    ProjectId,
    QualityAxes,
    StrategyKind,
)
from htop_tycoon.engine.endings import EndingKind, LegacyScore

SCHEMA_VERSION: int = 2


class PersistenceVersionError(ValueError):
    """Raised when a persisted document's version is unknown or missing."""


def _score_to_dict(score: LegacyScore) -> dict[str, Any]:
    return {
        "ending_kind": score.ending_kind.value,
        "ending_year": score.ending_year,
        "ending_cash_cents": score.ending_cash_cents,
        "total_fans": score.total_fans,
        "games_shipped": score.games_shipped,
        "mega_hits": score.mega_hits,
    }


def _state_to_dict(state: CompanyState) -> dict[str, Any]:
    return {
        "year": state.year,
        "day_index": state.day_index,
        "cash": state.cash.cents,
        "fans": state.fans,
        "strategy": state.strategy.value,
        "auto_on": state.auto_on,
        "speed": state.speed,
        "rng_seed": state.rng_seed,
        "games_shipped": state.games_shipped,
        "mega_hits": state.mega_hits,
        "own_console": None if state.own_console is None else state.own_console.value,
        "voluntary_sale_pending": state.voluntary_sale_pending,
        "legacy_scores": [_score_to_dict(s) for s in state.legacy_scores],
        "employees": [
            {
                "id": int(emp.id),
                "name": emp.name,
                "job": emp.job.value,
                "level": emp.level,
                "salary": emp.salary.cents,
                "satisfaction": emp.satisfaction,
                "dept": emp.dept.value,
            }
            for emp in state.employees.values()
        ],
        "projects": [
            {
                "id": int(proj.id),
                "title": str(proj.title),
                "genre": proj.genre.value,
                "platform": proj.platform.value,
                "console": None if proj.console is None else proj.console.value,
                "progress": proj.progress.value,
                "quality": {
                    "fun": proj.quality.fun,
                    "graphics": proj.quality.graphics,
                    "sound": proj.quality.sound,
                    "originality": proj.quality.originality,
                },
                "days_in_dev": proj.days_in_dev,
                "lead_id": None if proj.lead_id is None else int(proj.lead_id),
                "team_ids": [int(eid) for eid in proj.team_ids],
                "units_sold": proj.units_sold,
                "hall_of_fame": proj.hall_of_fame,
            }
            for proj in state.projects.values()
        ],
    }


def to_yaml(state: CompanyState) -> str:
    """Serialize CompanyState to a YAML string with a version header."""
    document = {"version": SCHEMA_VERSION, "state": _state_to_dict(state)}
    return yaml.safe_dump(
        document, sort_keys=False, allow_unicode=True, default_flow_style=False
    )


def _coerce_employee(raw: dict[str, Any]) -> Employee:
    return Employee(
        id=EmployeeId(int(raw["id"])),
        name=str(raw["name"]),
        job=Job(str(raw["job"])),
        level=int(raw["level"]),
        salary=Money(int(raw["salary"])),
        satisfaction=int(raw["satisfaction"]),
        dept=Department(str(raw["dept"])),
    )


def _coerce_project(raw: dict[str, Any]) -> GameProject:
    console_raw = raw.get("console")
    console: Console | None = None if console_raw is None else Console(str(console_raw))
    lead_id_raw = raw.get("lead_id")
    lead_id: EmployeeId | None = None if lead_id_raw is None else EmployeeId(int(lead_id_raw))
    quality_raw = raw["quality"]
    return GameProject(
        id=ProjectId(int(raw["id"])),
        title=GameTitle(str(raw["title"])),
        genre=Genre(str(raw["genre"])),
        platform=Platform(str(raw["platform"])),
        console=console,
        progress=Progress(int(raw["progress"])),
        quality=QualityAxes(
            int(quality_raw["fun"]),
            int(quality_raw["graphics"]),
            int(quality_raw["sound"]),
            int(quality_raw["originality"]),
        ),
        days_in_dev=int(raw["days_in_dev"]),
        lead_id=lead_id,
        team_ids=tuple(EmployeeId(int(x)) for x in raw["team_ids"]),
        units_sold=int(raw.get("units_sold", 0)),
        hall_of_fame=bool(raw.get("hall_of_fame", False)),
    )


def _coerce_state(raw: dict[str, Any]) -> CompanyState:
    own_console_raw = raw.get("own_console")
    own_console: Console | None = (
        None if own_console_raw is None else Console(str(own_console_raw))
    )
    state = CompanyState(
        year=int(raw["year"]),
        day_index=int(raw["day_index"]),
        cash=Money(int(raw["cash"])),
        fans=int(raw["fans"]),
        strategy=StrategyKind(str(raw["strategy"])),
        auto_on=bool(raw["auto_on"]),
        speed=int(raw["speed"]),
        rng_seed=int(raw["rng_seed"]),
        games_shipped=int(raw.get("games_shipped", 0)),
        mega_hits=int(raw.get("mega_hits", 0)),
        own_console=own_console,
        voluntary_sale_pending=bool(raw.get("voluntary_sale_pending", False)),
    )
    for emp_raw in raw.get("employees", []):
        emp = _coerce_employee(emp_raw)
        state = state.add_employee(emp)
    for proj_raw in raw.get("projects", []):
        proj = _coerce_project(proj_raw)
        state = state.add_project(proj)
    for score_raw in raw.get("legacy_scores", []):
        from htop_tycoon.engine.endings import EndingKind, LegacyScore

        state = state.append_legacy_score(
            LegacyScore(
                ending_kind=EndingKind(str(score_raw["ending_kind"])),
                ending_year=int(score_raw["ending_year"]),
                ending_cash_cents=int(score_raw["ending_cash_cents"]),
                total_fans=int(score_raw["total_fans"]),
                games_shipped=int(score_raw["games_shipped"]),
                mega_hits=int(score_raw["mega_hits"]),
            )
        )
    return state


def from_yaml(text: str) -> CompanyState:
    """Deserialize a YAML document produced by to_yaml()."""
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        raise PersistenceVersionError(f"Top-level YAML must be a mapping, got {type(document).__name__}")
    version = document.get("version")
    if version is None:
        raise PersistenceVersionError("Missing 'version' field in save document")
    if version != SCHEMA_VERSION:
        raise PersistenceVersionError(
            f"Unsupported save version {version}; expected {SCHEMA_VERSION}"
        )
    state_raw = document.get("state")
    if not isinstance(state_raw, dict):
        raise PersistenceVersionError("Missing or invalid 'state' field in save document")
    return _coerce_state(state_raw)
