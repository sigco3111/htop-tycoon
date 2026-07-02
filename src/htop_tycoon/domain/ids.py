"""Branded IDs (EmployeeId, ProjectId, CompanyId) + validated GameTitle.

IDs subclass int so they remain hashable for dict keys and serializable as JSON
numbers, while the distinct class identity prevents cross-type confusion.
"""

from __future__ import annotations


class _BrandedInt(int):
    """Base class for branded int IDs. Equality is type-tagged so an
    EmployeeId(5) and a ProjectId(5) compare as different values.
    Hash is still the int value (so they remain usable as dict keys in
    type-keyed dicts).
    """

    _brand: str = ""

    def __new__(cls, value: int) -> _BrandedInt:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{cls.__name__} must wrap an int, got {type(value).__name__}")
        return super().__new__(cls, value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _BrandedInt):
            return type(self) is type(other) and int.__eq__(self, other)
        if isinstance(other, int):
            return int.__eq__(self, other)
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return False
        return not eq

    def __hash__(self) -> int:
        return int.__hash__(self)


class EmployeeId(_BrandedInt):
    """Branded int for employee identity."""

    _brand = "employee"


class ProjectId(_BrandedInt):
    """Branded int for project identity."""

    _brand = "project"


class CompanyId(_BrandedInt):
    """Branded int for company identity. Single instance per game for now."""

    _brand = "company"


class GameTitle(str):
    """Validated game title — must be non-empty after stripping."""

    def __new__(cls, value: str) -> GameTitle:
        if not isinstance(value, str):
            raise TypeError(f"GameTitle must be str, got {type(value).__name__}")
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"GameTitle must be non-empty, got {value!r}")
        instance = super().__new__(cls, stripped)
        return instance
