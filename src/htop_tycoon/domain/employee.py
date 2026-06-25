"""Domain: Employee aggregate (T5).

Pure data + immutable promotion / demotion helpers. No hiring or firing
logic lives here — those live in ``engine/actions.py`` (T10). All updates
go through ``dataclasses.replace`` so the instance remains frozen.

Salary tier math is sourced from ``balance.yaml`` (``money.salary_tier_multiplier``);
each tier step multiplies or divides the salary by that factor. The plan
locks the multiplier at ``1.25``.
"""

from __future__ import annotations

import dataclasses

from htop_tycoon.data import load_balance
from htop_tycoon.domain.state import DepartmentId, EmployeeId

__all__ = ["Employee"]


# Bounds from plan + balance.yaml. ``max_skill`` lives in balance.yaml under
# ``employees.max_skill`` (= 10); we hard-code the tier cap (1..5) here because
# the plan fixes the tier range at [1, 5] and balance.yaml does not expose it.
SKILL_MIN: int = 1
SKILL_MAX: int = 10
TIER_MIN: int = 1
TIER_MAX: int = 5
SATISFACTION_MIN: int = 0
SATISFACTION_MAX: int = 100


def _validate_strict_int(name: str, value: object) -> int:
    """Validate ``value`` is a built-in ``int`` (rejecting ``bool`` and ``float``)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{name} must be a strict int, got {type(value).__name__}: {value!r}"
        )
    return value


def _validate_in_range(name: str, value: int, lo: int, hi: int) -> int:
    """Validate ``lo <= value <= hi``."""
    if not lo <= value <= hi:
        raise ValueError(
            f"{name} must be in [{lo}, {hi}], got {value!r}"
        )
    return value


def _salary_tier_multiplier() -> float:
    """Return the salary tier multiplier from ``balance.yaml``.

    Read at call time so test changes to balance (or future balance
    refactors) are honored. The default in ``balance.yaml`` is 1.25.
    """
    balance = load_balance()
    return float(balance["money"]["salary_tier_multiplier"])


@dataclasses.dataclass(frozen=True, slots=True)
class Employee:
    """A company employee.

    Attributes:
        id: Stable identifier (e.g. ``"emp-001"``).
        name: Display name (Korean or English).
        dept_id: The department this employee belongs to.
        skill: Skill rating in ``[1, 10]`` (matches ``employees.max_skill``).
            Read by T8's SECRET ending (``all_employees_skill == max_skill``).
        tier: Job tier in ``[1, 5]`` (e.g. intern -> CEO). Higher tier = higher salary.
        salary_per_week: Weekly salary in currency units (non-negative int).
        satisfaction: Happiness in ``[0, 100]``. Below ``zombie_satisfaction_threshold``
            the engine flags the employee as a quitting risk.
        hired_tick: Game tick at which the employee was hired (non-negative int).
    """

    id: EmployeeId
    name: str
    dept_id: DepartmentId
    skill: int
    tier: int
    salary_per_week: int
    satisfaction: int
    hired_tick: int

    def __post_init__(self) -> None:
        _validate_in_range("skill", _validate_strict_int("skill", self.skill), SKILL_MIN, SKILL_MAX)
        _validate_in_range("tier", _validate_strict_int("tier", self.tier), TIER_MIN, TIER_MAX)
        _validate_strict_int("salary_per_week", self.salary_per_week)
        if self.salary_per_week < 0:
            raise ValueError(
                f"salary_per_week must be non-negative, got {self.salary_per_week!r}"
            )
        _validate_in_range(
            "satisfaction",
            _validate_strict_int("satisfaction", self.satisfaction),
            SATISFACTION_MIN,
            SATISFACTION_MAX,
        )
        _validate_strict_int("hired_tick", self.hired_tick)
        if self.hired_tick < 0:
            raise ValueError(
                f"hired_tick must be non-negative, got {self.hired_tick!r}"
            )

    # ---- pure promotion / demotion helpers -----------------------------

    def promote(self) -> Employee:
        """Return a new ``Employee`` with ``tier + 1`` and salary ``*`` multiplier.

        Pure function: does NOT mutate ``self``. Raises ``ValueError`` if
        already at ``TIER_MAX``.
        """
        if self.tier >= TIER_MAX:
            raise ValueError(
                f"cannot promote: tier {self.tier} is already at max {TIER_MAX}"
            )
        multiplier = _salary_tier_multiplier()
        new_salary = int(round(self.salary_per_week * multiplier))
        return dataclasses.replace(self, tier=self.tier + 1, salary_per_week=new_salary)

    def demote(self) -> Employee:
        """Return a new ``Employee`` with ``tier - 1`` (floored at ``TIER_MIN``).

        Pure function: does NOT mutate ``self``. If already at ``TIER_MIN``,
        returns a new employee with the same tier and unchanged salary (no
        further demotion possible). When demotion does occur, salary is
        divided by the multiplier.
        """
        if self.tier <= TIER_MIN:
            # Floor: cannot demote below tier 1; return a copy with no changes.
            return dataclasses.replace(self)
        multiplier = _salary_tier_multiplier()
        new_salary = int(round(self.salary_per_week / multiplier))
        return dataclasses.replace(self, tier=self.tier - 1, salary_per_week=new_salary)
