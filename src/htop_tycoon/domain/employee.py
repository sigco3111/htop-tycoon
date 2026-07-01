"""htop-tycoon v3.0 — Employee domain dataclass. Spec §2.5 + §5.3.

A frozen dataclass representing a single employee of the studio. Domain
immutability is enforced via ``frozen=True``; the only mutation path is
``dataclasses.replace(employee, **changes)`` (spec §5.3).

Derived fields ``salary_daily`` and ``skill_per_axis`` are computed from
``(job, level)`` in ``__post_init__`` and are marked ``init=False`` so
they don't pollute the constructor signature. They are set via
``object.__setattr__`` (the only way to mutate a frozen dataclass).

HW_ENGINEER (the prestige job, post-Secret) is rejected at construction
time because it has no entry in ``_JOB_INDEX_ORDER`` and therefore no
``nice_value`` slot (spec §4.1.1). It must be spawned via a dedicated
path (Wave 5+).

Anti-pattern guards (per AGENTS.md §8):
  - No ``import random`` — GameRNG is the only randomness gateway.
  - No I/O, no clock access — pure values only.
  - Salary base rates live in ``balance.yaml``; this module mirrors them
    as ``_BASE_SALARY_DAILY`` with a comment that the data loader
    (T33+) will replace the hardcoded literal.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from types import MappingProxyType

from htop_tycoon.domain.enums import (
    _JOB_QUALITY_CONTRIBUTIONS,
    _PER_LEVEL_LINEAR_BONUS,
    Department,
    JobType,
    QualityAxis,
    nice_value,
)
from htop_tycoon.domain.ids import EmployeeId

# Spec §2.5: base salaries per JobType. Mirrored from data/balance.yaml at
# runtime in Wave 5+; for now, hard-coded mirror (balance.yaml is the
# canonical source). The data loader (T33+) will replace this module-level
# constant with a runtime lookup.
_BASE_SALARY_DAILY: MappingProxyType[JobType, int] = MappingProxyType({
    JobType.PRODUCER: 400,
    JobType.GAME_DESIGNER: 300,
    JobType.PROGRAMMER: 320,
    JobType.GRAPHIC_ARTIST: 280,
    JobType.SOUND_CREATOR: 260,
    JobType.HACKER: 350,
    JobType.HW_ENGINEER: 500,
})


def _salary_for(job: JobType, level: int) -> int:
    """Spec §2.5: salary = base * 1.2^(level - 1). Level 1 = 1.0x, level 5 = 2.0736x."""
    base = _BASE_SALARY_DAILY[job]
    # Round to int; daily salary is whole G (per AGENTS.md: salaries are G integers).
    return int(round(base * (1.2 ** (level - 1))))


def _skill_per_axis_for(job: JobType, level: int) -> MappingProxyType[QualityAxis, float]:
    """Per-job quality contribution x level multiplier.

    Spec §2.5: skill scales linearly per level above 1:
        contribution * (1.0 + _PER_LEVEL_LINEAR_BONUS * (level - 1))
    Immutable view so callers cannot mutate the skill map.

    Note: HW_ENGINEER has an empty contribution table, so this returns an
    empty MappingProxyType for it. The Employee constructor rejects
    HW_ENGINEER so this branch is never reached via Employee.
    """
    base_table = _JOB_QUALITY_CONTRIBUTIONS[job]
    multiplier = 1.0 + _PER_LEVEL_LINEAR_BONUS * (level - 1)
    skills = {
        axis: weight * multiplier
        for axis, weight in base_table.items()
    }
    return MappingProxyType(skills)


@dataclass(frozen=True, slots=True)
class Employee:
    """An employee of the company. Spec §2.5 + §5.3.

    Frozen dataclass (spec §5.3: domain is immutable except via
    ``dataclasses.replace(employee, **changes)``).
    """

    id: EmployeeId
    name: str  # Korean display name (per AGENTS.md §1 — Korean UI default)
    dept: Department
    job: JobType
    level: int = 1  # 1..5 inclusive
    satisfaction: float = 0.6  # 0.0..1.0; <= 0.20 = zombie (spec §1.3 / balance.yaml)
    joined_day: int = 1
    salary_daily: int = field(init=False)
    skill_per_axis: MappingProxyType[QualityAxis, float] = field(init=False)

    def __post_init__(self) -> None:
        # Spec §2.5: 5 levels per job, job_change_multiplier 1.2.
        if not 1 <= self.level <= 5:
            raise ValueError(f"level must be in 1..5 (spec §2.5); got {self.level}")
        if not 0.0 <= self.satisfaction <= 1.0:
            raise ValueError(f"satisfaction must be in 0.0..1.0; got {self.satisfaction}")
        if self.job is JobType.HW_ENGINEER:
            raise ValueError(
                "HW_ENGINEER is a prestige job (spec §2.5, post-Secret) and "
                "has no entry in _JOB_INDEX_ORDER; spawn it via a separate path."
            )
        # Init-only fields are computed via __setattr__ because of frozen=True.
        object.__setattr__(self, "salary_daily", _salary_for(self.job, self.level))
        object.__setattr__(self, "skill_per_axis", _skill_per_axis_for(self.job, self.level))

    @property
    def nice_value(self) -> int:
        """Compute htop-style nice value (spec §4.1.1).

        Delegates to the module-level helper; uses job.job_index.
        Returns int in [-20, +19] (HW_ENGINEER is unreachable here because the
        constructor rejects it).
        """
        return nice_value(self.job.job_index, self.level)

    @property
    def is_unsatisfied(self) -> bool:
        """True if employee satisfaction dropped to the zombie threshold."""
        return self.satisfaction <= 0.20  # balance.yaml zombie.satisfaction_threshold

    @property
    def is_prestige(self) -> bool:
        """True for the prestige job (HW_ENGINEER; spec §2.5).

        Note: the constructor rejects HW_ENGINEER, so this is always False
        for a successfully-constructed Employee. Kept for forward-compat
        with the post-Secret prestige path.
        """
        return self.job.is_prestige

    def change_job(self, new_job: JobType, job_change_multiplier: float = 1.2) -> Employee:
        """Spec §2.5: changing job multiplies salary by job_change_multiplier.

        Returns a new Employee; hw_engineer cannot be assigned via this path
        (constructor guard). Level is preserved; ``skill_per_axis`` is
        recomputed for ``(new_job, level)`` by ``__post_init__`` on the
        new instance.

        Implementation note: ``salary_daily`` and ``skill_per_axis`` are
        ``init=False`` (derived in __post_init__), so they cannot be passed
        to ``dataclasses.replace``. We do a two-step: replace the (valid)
        init=True fields, then override the derived salary via
        ``object.__setattr__`` (the only way to mutate a frozen dataclass).
        """
        new_emp = dataclasses.replace(self, job=new_job)
        object.__setattr__(
            new_emp,
            "salary_daily",
            int(round(self.salary_daily * job_change_multiplier)),
        )
        return new_emp

    def apply_level_up(self) -> Employee:
        """Return new Employee with level+1 (capped at 5).

        Raises ValueError if already at max level. The new salary/skill
        are recomputed by ``__post_init__`` on the new instance (``replace``
        re-invokes the constructor).
        """
        if self.level >= 5:
            raise ValueError("Employee is already at max level (5); spec §2.5")
        return dataclasses.replace(self, level=self.level + 1)


__all__ = ["Employee"]
