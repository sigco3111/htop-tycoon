"""CompanyState — the single aggregate root for the game's full state.

NOT frozen — holds mutable employee/project dicts. Every "mutation" returns
a new CompanyState via dataclasses.replace with a shallow copy of the dicts,
preserving the value-object semantics while allowing the dicts themselves
to grow/shrink.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.enums import Console, Genre, StrategyKind
from htop_tycoon.domain.ids import EmployeeId, ProjectId
from htop_tycoon.domain.money import Money
from htop_tycoon.domain.project import GameProject

if TYPE_CHECKING:
    from htop_tycoon.engine.endings import LegacyScore

YEAR_LENGTH_DAYS: int = 365
DEFAULT_RNG_SEED: int = 42
DEFAULT_STARTING_CASH_CENTS: int = 100_000_00

MIN_YEAR: int = 1
MIN_SPEED: int = 0  # 0 = paused (per README); 1-3 = user speeds; 4 = headless QA
MAX_SPEED: int = 4


@dataclass(slots=True)
class CompanyState:
    year: int = MIN_YEAR
    day_index: int = 0
    cash: Money = Money(DEFAULT_STARTING_CASH_CENTS)
    fans: int = 0
    strategy: StrategyKind = StrategyKind.BALANCED
    auto_on: bool = False
    speed: int = MIN_SPEED
    employees: dict[EmployeeId, Employee] = field(default_factory=dict)
    projects: dict[ProjectId, GameProject] = field(default_factory=dict)
    rng_seed: int = DEFAULT_RNG_SEED
    games_shipped: int = 0
    mega_hits: int = 0
    own_console: Console | None = None
    voluntary_sale_pending: bool = False
    legacy_scores: tuple[LegacyScore, ...] = ()
    focus_genre: Genre | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.year, int) or self.year < MIN_YEAR:
            raise ValueError(f"year must be int >= {MIN_YEAR}, got {self.year}")
        if not isinstance(self.cash, Money):
            raise TypeError(f"cash must be Money, got {type(self.cash).__name__}")
        if not isinstance(self.speed, int) or not (MIN_SPEED <= self.speed <= MAX_SPEED):
            raise ValueError(
                f"speed must be int in [{MIN_SPEED}, {MAX_SPEED}], got {self.speed}"
            )
        if self.day_index < 0:
            raise ValueError(f"day_index must be >= 0, got {self.day_index}")
        if self.day_index >= YEAR_LENGTH_DAYS:
            raise ValueError(
                f"day_index must be < {YEAR_LENGTH_DAYS}, got {self.day_index}"
            )

    def advance_day(self) -> CompanyState:
        new_day = self.day_index + 1
        if new_day >= YEAR_LENGTH_DAYS:
            return dataclasses.replace(
                self,
                year=self.year + 1,
                day_index=0,
            )
        return dataclasses.replace(self, day_index=new_day)

    def add_employee(self, employee: Employee) -> CompanyState:
        if employee.id in self.employees:
            raise ValueError(f"employee {employee.id} already in company")
        new_employees = dict(self.employees)
        new_employees[employee.id] = employee
        return dataclasses.replace(self, employees=new_employees)

    def remove_employee(self, employee_id: EmployeeId) -> CompanyState:
        if employee_id not in self.employees:
            return self
        new_employees = dict(self.employees)
        del new_employees[employee_id]
        return dataclasses.replace(self, employees=new_employees)

    def add_project(self, project: GameProject) -> CompanyState:
        if project.id in self.projects:
            raise ValueError(f"project {project.id} already in company")
        new_projects = dict(self.projects)
        new_projects[project.id] = project
        return dataclasses.replace(self, projects=new_projects)

    def remove_project(self, project_id: ProjectId) -> CompanyState:
        if project_id not in self.projects:
            return self
        new_projects = dict(self.projects)
        del new_projects[project_id]
        return dataclasses.replace(self, projects=new_projects)

    def set_strategy(self, strategy: StrategyKind) -> CompanyState:
        return dataclasses.replace(self, strategy=strategy)

    def set_speed(self, speed: int) -> CompanyState:
        if not isinstance(speed, int) or not (MIN_SPEED <= speed <= MAX_SPEED):
            raise ValueError(
                f"speed must be int in [{MIN_SPEED}, {MAX_SPEED}], got {speed}"
            )
        return dataclasses.replace(self, speed=speed)

    def toggle_auto(self) -> CompanyState:
        return dataclasses.replace(self, auto_on=not self.auto_on)

    def adjust_cash(self, delta: Money) -> CompanyState:
        return dataclasses.replace(self, cash=self.cash + delta)

    def add_fans(self, delta: int) -> CompanyState:
        return dataclasses.replace(self, fans=max(0, self.fans + delta))

    def list_employees(self) -> Iterable[Employee]:
        return self.employees.values()

    def list_projects(self) -> Iterable[GameProject]:
        return self.projects.values()

    def increment_games_shipped(self) -> CompanyState:
        return dataclasses.replace(self, games_shipped=self.games_shipped + 1)

    def increment_mega_hits(self) -> CompanyState:
        return dataclasses.replace(self, mega_hits=self.mega_hits + 1)

    def mark_own_console(self, console: Console) -> CompanyState:
        return dataclasses.replace(self, own_console=console)

    def set_voluntary_sale_pending(self, flag: bool) -> CompanyState:
        return dataclasses.replace(self, voluntary_sale_pending=flag)

    def append_legacy_score(self, score: LegacyScore) -> CompanyState:
        new_scores: tuple[LegacyScore, ...] = (*self.legacy_scores, score)
        return dataclasses.replace(self, legacy_scores=new_scores)

    def set_focus_genre(self, genre: Genre | None) -> CompanyState:
        return dataclasses.replace(self, focus_genre=genre)
