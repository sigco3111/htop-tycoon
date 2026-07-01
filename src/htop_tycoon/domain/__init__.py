"""htop-tycoon v3.0 — domain layer.

Pure, serializable types shared by the engine and the UI:
  - Enumerations (department, job, quality axis, platform, ending, action)
  - Opaque ID types and their UUID4 factories
  - Pure helpers (nice_value, quality_weight, JOBS_BY_DEPARTMENT)
  - Aggregate dataclasses (GameProject, ConsoleMarket, Market, Event, GameState, ...)

This package depends on nothing else in the project. The engine imports
from here; the UI imports from here. Nothing imports from the engine or
the UI back into here (spec §5.3, engine → UI one-way only).

Public API (re-exported here for ``from htop_tycoon.domain import ...``):

  Enumerations:
    - Department      (5 members)
    - JobType         (7 members: 6 base + HW_ENGINEER prestige)
    - QualityAxis     (4 members)
    - Platform        (5 members)
    - EndingKind      (5 members)
    - ActionKind      (typing.Literal — 9 values per spec §3.2.1)

  Helpers:
    - nice_value(job_index, level) -> int
    - quality_weight(job_index, level, axis) -> float
    - JOBS_BY_DEPARTMENT: dict[Department, list[JobType]]

  IDs:
    - EntityId, EmployeeId, ProjectId, ConsoleId, GenreId,
      ThemeId, PlatformId, DeptId
    - new_*_id() factories for each

  Aggregates:
    - Employee        — single hire (spec §2.5)
    - GameProject     — a single game project (spec §2.2)
    - ConsoleMarket   — per-console market state (spec §2.3, §2.8)
    - Market          — top-level market state container (spec §2.6)
    - Event / EventKind — event bus payload (spec §5.3)
    - LegacyScore / AchievementUnlock
    - Ending
    - GameState       — single serialization boundary root (spec §5.3)
    - compute_game_state_hash() — spec §7.3 deterministic hash
"""
from htop_tycoon.domain.console_market import ConsoleMarket
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.ending import Ending
from htop_tycoon.domain.enums import (
    JOBS_BY_DEPARTMENT,
    ActionKind,
    Department,
    EndingKind,
    JobType,
    Platform,
    QualityAxis,
    nice_value,
    quality_weight,
)
from htop_tycoon.domain.event import Event, EventKind
from htop_tycoon.domain.ids import (
    ConsoleId,
    DeptId,
    EmployeeId,
    EntityId,
    GenreId,
    PlatformId,
    ProjectId,
    ThemeId,
    new_console_id,
    new_dept_id,
    new_employee_id,
    new_genre_id,
    new_platform_id,
    new_project_id,
    new_theme_id,
)
from htop_tycoon.domain.legacy import AchievementUnlock, LegacyScore
from htop_tycoon.domain.market import Market
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.state import (
    DEFAULT_RNG_SEED,
    DEFAULT_STARTING_CASH,
    GameState,
    compute_game_state_hash,
)

__all__ = [
    # Enumerations
    "ActionKind",
    "Department",
    "EndingKind",
    "JobType",
    "JOBS_BY_DEPARTMENT",
    "Platform",
    "QualityAxis",
    # Helpers
    "nice_value",
    "quality_weight",
    # ID types
    "ConsoleId",
    "DeptId",
    "EmployeeId",
    "EntityId",
    "GenreId",
    "PlatformId",
    "ProjectId",
    "ThemeId",
    # ID factories
    "new_console_id",
    "new_dept_id",
    "new_employee_id",
    "new_genre_id",
    "new_platform_id",
    "new_project_id",
    "new_theme_id",
    # Aggregate dataclasses
    "AchievementUnlock",
    "ConsoleMarket",
    "DEFAULT_RNG_SEED",
    "DEFAULT_STARTING_CASH",
    "Employee",
    "Ending",
    "Event",
    "EventKind",
    "GameProject",
    "GameState",
    "LegacyScore",
    "Market",
    "compute_game_state_hash",
]
