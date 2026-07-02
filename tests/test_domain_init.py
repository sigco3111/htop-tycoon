"""T4.1 RED: domain barrel — every public type must re-export cleanly."""

from __future__ import annotations

import pytest

EXPECTED_PUBLIC_TYPES: tuple[str, ...] = (
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
)


def test_reexports_all_public_types() -> None:
    import htop_tycoon.domain as dom

    for name in EXPECTED_PUBLIC_TYPES:
        assert hasattr(dom, name), f"htop_tycoon.domain.{name} not re-exported"


def test_reexports_are_correct_objects() -> None:
    from htop_tycoon.domain import (
        CompanyState,
        Employee,
        GameProject,
        GameRng,
        Money,
    )

    assert CompanyState.__name__ == "CompanyState"
    assert Money.__name__ == "Money"
    assert Employee.__name__ == "Employee"
    assert GameProject.__name__ == "GameProject"
    assert GameRng.__name__ == "GameRng"


def test_no_internals_leaked() -> None:
    """Internal helpers (_clamp, _BASE_SALARY_CENTS, etc.) must NOT be re-exported."""
    with pytest.raises(ImportError):
        from htop_tycoon.domain import _clamp  # type: ignore[attr-defined]  # noqa: F401


def test_all_exports_listed_in_all() -> None:
    import htop_tycoon.domain as dom

    assert hasattr(dom, "__all__"), "htop_tycoon.domain must define __all__"
    assert set(dom.__all__) == set(EXPECTED_PUBLIC_TYPES), (
        f"__all__ mismatch.\n"
        f"  Missing: {set(EXPECTED_PUBLIC_TYPES) - set(dom.__all__)}\n"
        f"  Extra:   {set(dom.__all__) - set(EXPECTED_PUBLIC_TYPES)}"
    )
