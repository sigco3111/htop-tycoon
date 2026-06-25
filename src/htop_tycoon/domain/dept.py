"""Domain: Department aggregate + DepartmentType enum (T5).

Pure data only. No business logic (no hiring, no firing, no revenue split)
lives here — those live in ``engine/actions.py`` (T10). The Department is
strictly frozen; updates happen via ``dataclasses.replace``.

The ``unlocked`` flag is read by T8's SECRET ending condition
(``all_depts_unlocked``), so this module is part of the SECRET gate.
"""

from __future__ import annotations

import dataclasses
from enum import Enum

from htop_tycoon.domain.state import DepartmentId, EmployeeId

__all__ = ["Department", "DepartmentType"]


class DepartmentType(Enum):
    """The 5 locked department types.

    Locked at 5 by the plan ("Limit scope: no more than 5 ... departments.
    Violations require plan revision"). Adding a sixth value requires a
    plan update first.
    """

    Engineering = "Engineering"
    Sales = "Sales"
    Operations = "Operations"
    Marketing = "Marketing"
    Finance = "Finance"


def _validate_employee_ids_unique(value: object) -> list[EmployeeId]:
    """Validate Department.employee_ids: a list of EmployeeId with no duplicates."""
    if not isinstance(value, list):
        raise ValueError(
            f"employee_ids must be a list, got {type(value).__name__}: {value!r}"
        )
    for item in value:
        if not isinstance(item, str):
            raise ValueError(
                f"employee_ids must contain EmployeeId (str), got "
                f"{type(item).__name__}: {item!r}"
            )
    seen: set[str] = set()
    for item in value:
        if item in seen:
            raise ValueError(f"employee_ids contains duplicate EmployeeId: {item!r}")
        seen.add(item)
    # Cast at the boundary: trust the parsed value, narrow to EmployeeId list.
    return [EmployeeId(item) for item in value]


def _validate_founded_tick(value: object) -> int:
    """Validate Department.founded_tick: strict int (>= 0; founded ticks are non-negative)."""
    # ``bool`` is a subclass of ``int`` in Python; reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"founded_tick must be a strict int, got {type(value).__name__}: {value!r}"
        )
    if value < 0:
        raise ValueError(f"founded_tick must be non-negative, got {value!r}")
    return value


def _validate_head_in_employees(
    head: EmployeeId | None, employees: list[EmployeeId]
) -> None:
    """Validate that ``head`` (if not None) is one of the ``employees``."""
    if head is None:
        return
    if head not in employees:
        raise ValueError(
            f"head_employee_id {head!r} must be in employee_ids "
            f"{employees!r}"
        )


@dataclasses.dataclass(frozen=True, slots=True)
class Department:
    """A company department.

    Attributes:
        id: Stable identifier (e.g. ``"dept-eng"``).
        type: The department kind (Engineering / Sales / Operations / Marketing / Finance).
        head_employee_id: The leading employee of this department, or ``None`` if
            the department has no head yet (e.g. just founded, not staffed).
        employee_ids: Members of this department. Must contain no duplicates and,
            if ``head_employee_id`` is set, must include it.
        founded_tick: The game tick at which this department was created
            (non-negative strict int).
        unlocked: Whether the department is unlocked (T8 SECRET ending reads this
            flag as ``all_depts_unlocked``). Defaults to ``False``.
    """

    id: DepartmentId
    type: DepartmentType
    head_employee_id: EmployeeId | None
    employee_ids: list[EmployeeId]
    founded_tick: int
    unlocked: bool = False

    def __post_init__(self) -> None:
        validated_ids = _validate_employee_ids_unique(self.employee_ids)
        _validate_founded_tick(self.founded_tick)
        _validate_head_in_employees(self.head_employee_id, validated_ids)
        # Re-bind the cleaned list onto the frozen instance via __setattr__.
        # The list is freshly constructed above, so no in-place mutation occurred.
        object.__setattr__(self, "employee_ids", validated_ids)
