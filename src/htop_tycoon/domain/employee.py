"""Employee entity + Salary + compute_salary.

Employee is the primary unit of the company's workforce. Frozen dataclass
so all "mutations" (promote, salary adjustment) return new instances —
preserves the domain's value-object semantics and makes hashability safe.
"""

from __future__ import annotations

from dataclasses import dataclass

from htop_tycoon.domain.enums import Department, Job
from htop_tycoon.domain.ids import EmployeeId
from htop_tycoon.domain.money import Money


@dataclass(frozen=True, slots=True)
class Salary:
    amount: Money
    tier: int


# Base monthly salary in cents per Job. Engine multiplies by level factor.
_BASE_SALARY_CENTS: dict[Job, int] = {
    Job.JUNIOR: 200_00,
    Job.SENIOR: 350_00,
    Job.LEAD: 550_00,
    Job.ARTIST: 280_00,
    Job.DESIGNER: 300_00,
    Job.SOUND_ENGINEER: 270_00,
    Job.PRODUCER: 400_00,
    Job.QA: 180_00,
}

# Job tier — used by engine to bucket productivity bonuses.
_JOB_TIER: dict[Job, int] = {
    Job.JUNIOR: 1,
    Job.SENIOR: 2,
    Job.LEAD: 3,
    Job.ARTIST: 2,
    Job.DESIGNER: 2,
    Job.SOUND_ENGINEER: 2,
    Job.PRODUCER: 3,
    Job.QA: 1,
}

LEVEL_MULTIPLIER_BASE: float = 1.0
LEVEL_MULTIPLIER_PER_LEVEL: float = 0.15

MIN_LEVEL: int = 1
MAX_LEVEL: int = 10

PROMOTION_RAISE_FACTOR: float = 1.15

SATISFACTION_MIN: int = 0
SATISFACTION_MAX: int = 100
SATISFACTION_ZOMBIE_THRESHOLD: int = 20


def compute_salary(job: Job, level: int) -> Salary:
    """Deterministic salary from (job, level).

    Higher job tiers and higher levels both increase pay. Tier is the
    job's bucket (used by engine to compute productivity bonuses).
    """
    if not (MIN_LEVEL <= level <= MAX_LEVEL):
        raise ValueError(f"level {level} not in [{MIN_LEVEL}, {MAX_LEVEL}]")
    base = _BASE_SALARY_CENTS[job]
    multiplier = LEVEL_MULTIPLIER_BASE + (level - 1) * LEVEL_MULTIPLIER_PER_LEVEL
    amount_cents = int(round(base * multiplier))
    return Salary(amount=Money(amount_cents), tier=_JOB_TIER[job])


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


@dataclass(frozen=True, slots=True)
class Employee:
    id: EmployeeId
    name: str
    job: Job
    level: int
    salary: Money
    satisfaction: int
    dept: Department

    def __post_init__(self) -> None:
        if not isinstance(self.id, EmployeeId):
            raise TypeError(f"id must be EmployeeId, got {type(self.id).__name__}")
        if not isinstance(self.name, str):
            raise TypeError(f"name must be str, got {type(self.name).__name__}")
        if not self.name:
            raise ValueError("name must be non-empty")
        if not (MIN_LEVEL <= self.level <= MAX_LEVEL):
            raise ValueError(
                f"level {self.level} not in [{MIN_LEVEL}, {MAX_LEVEL}]"
            )
        if not isinstance(self.salary, Money):
            raise TypeError(f"salary must be Money, got {type(self.salary).__name__}")
        clamped_satisfaction = _clamp(
            self.satisfaction, SATISFACTION_MIN, SATISFACTION_MAX
        )
        if clamped_satisfaction != self.satisfaction:
            object.__setattr__(self, "satisfaction", clamped_satisfaction)

    @property
    def is_zombie(self) -> bool:
        return self.satisfaction < SATISFACTION_ZOMBIE_THRESHOLD

    def promote(self) -> Employee:
        if self.level >= MAX_LEVEL:
            raise ValueError(f"employee at max level ({MAX_LEVEL}) cannot promote")
        new_level = self.level + 1
        new_salary = Money(int(round(self.salary.cents * PROMOTION_RAISE_FACTOR)))
        return Employee(
            id=self.id,
            name=self.name,
            job=self.job,
            level=new_level,
            salary=new_salary,
            satisfaction=self.satisfaction,
            dept=self.dept,
        )
