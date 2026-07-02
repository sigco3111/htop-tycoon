"""compute_employee_productivity — pure function from Employee + GameRng to float.

Formula: tier × (level / MAX_LEVEL) × (satisfaction / 100) × jitter
where jitter = rng.int_range(90, 110) / 100.

Deterministic given same inputs.
"""

from __future__ import annotations

from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.enums import Job
from htop_tycoon.domain.rng import GameRng

JOB_TIER: dict[Job, int] = {
    Job.JUNIOR: 1,
    Job.SENIOR: 2,
    Job.LEAD: 3,
    Job.ARTIST: 2,
    Job.DESIGNER: 2,
    Job.SOUND_ENGINEER: 2,
    Job.PRODUCER: 3,
    Job.QA: 1,
}

MAX_LEVEL: int = 10
MAX_TIER: int = 3
JITTER_MIN: int = 90
JITTER_MAX: int = 110
JITTER_DIVISOR: int = 100


def compute_employee_productivity(employee: Employee, rng: GameRng) -> float:
    """Return productivity 0.0..~1.32 (jitter can overshoot 1.0 slightly)."""
    if employee.satisfaction <= 0:
        return 0.0
    tier = JOB_TIER[employee.job]
    level_factor = employee.level / MAX_LEVEL
    satisfaction_factor = employee.satisfaction / 100.0
    tier_factor = tier / MAX_TIER
    jitter = rng.int_range(JITTER_MIN, JITTER_MAX) / JITTER_DIVISOR
    return tier_factor * level_factor * satisfaction_factor * jitter
