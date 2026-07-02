"""Domain layer: pure data types for the game state, engine, and persistence.

Public API re-exports — every type listed in `__all__` is accessible as
`htop_tycoon.domain.<Name>`. Internal helpers (_clamp, _BASE_SALARY_CENTS,
etc.) stay private to their submodules.
"""

from __future__ import annotations

from htop_tycoon.domain.employee import Employee, Salary, compute_salary
from htop_tycoon.domain.enums import (
    Console,
    Department,
    Genre,
    Job,
    Platform,
    SatisfactionTier,
    StrategyKind,
)
from htop_tycoon.domain.ids import CompanyId, EmployeeId, GameTitle, ProjectId
from htop_tycoon.domain.money import ZERO, Money
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.quality import Progress, QualityAxes
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.domain.state import (
    DEFAULT_RNG_SEED,
    YEAR_LENGTH_DAYS,
    CompanyState,
)

__all__ = [
    # Enums
    "Job",
    "Genre",
    "Platform",
    "Console",
    "Department",
    "SatisfactionTier",
    "StrategyKind",
    # IDs
    "EmployeeId",
    "ProjectId",
    "CompanyId",
    "GameTitle",
    # Value objects
    "Money",
    "ZERO",
    "QualityAxes",
    "Progress",
    "Salary",
    # Entities
    "Employee",
    "GameProject",
    "compute_salary",
    # Aggregate
    "CompanyState",
    # Constants
    "YEAR_LENGTH_DAYS",
    "DEFAULT_RNG_SEED",
    # RNG
    "GameRng",
]
