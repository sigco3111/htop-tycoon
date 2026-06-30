"""Domain: FocusType enum + FocusChoice dataclass (Wave 8 / T40).

Per-plan structure:

- 5 dept types x 4 options each = 14 FocusType members
  (one universal BALANCED plus three per-dept options).
- ``FocusChoice`` carries ``dept_id``, ``focus``, ``set_tick`` (used by
  T43 to enforce a 16-week cooldown between focus changes).
- ``FOCUS_TYPE_PER_DEPT`` is the canonical lookup keyed by dept-type
  NAME (str, not the DeptType enum) to avoid an import cycle
  (focus -> dept -> state -> focus). The mapping is at most additive
  to ``DepartmentType`` but kept string-keyed for module isolation.

These types travel through :class:`GameState` (``state.dept_focus``
mapping) and are pure data. The engine clamping logic lives in
``engine/dept_focus.py`` (T41).
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum
from typing import Final, TypeVar

T = TypeVar("T")


class FocusType(StrEnum):
    """Department-level strategic posture (T40).

    Locked to 14 members: BALANCED + 3 specific per dept type (5 dept
    types x 3 = 13). The cap of 13 is enforced by the
    :data:`FOCUS_TYPE_PER_DEPT` length check in tests/test_dept_focus.py.
    """

    # Universal — every dept can fall back to neutral (mod=1.0).
    BALANCED = "BALANCED"
    # Engineering-specific.
    QUALITY = "QUALITY"
    SPEED = "SPEED"
    COST = "COST"
    # Sales-specific.
    AGGRESSIVE = "AGGRESSIVE"
    CONSERVATIVE = "CONSERVATIVE"
    RELATIONSHIP = "RELATIONSHIP"
    # Operations-specific.
    EFFICIENCY = "EFFICIENCY"
    SAFETY = "SAFETY"
    SCALE = "SCALE"
    # Marketing-specific.
    BRAND = "BRAND"
    PERFORMANCE = "PERFORMANCE"
    VIRAL = "VIRAL"
    # Finance-specific.
    CONSERVATIVE_FIN = "CONSERVATIVE_FIN"
    GROWTH = "GROWTH"
    HEDGE = "HEDGE"


# Canonical dept-type NAME list (5 names — mirrors htop_tycoon.domain.dept.DepartmentType).
# We keep this string-keyed (not enum-keyed) to avoid the circular
# import focus -> dept -> state -> focus. The mapping is built
# lazily via ``get_focus_options_for_dept_type``.
_DEPT_TYPE_NAMES: Final[tuple[str, ...]] = (
    "Engineering",
    "Sales",
    "Operations",
    "Marketing",
    "Finance",
)


# Per-department focus options keyed by dept-type NAME. The cap of 4
# (BALANCED + 3 specific) per dept is enforced by tests/test_dept_focus.py.
FOCUS_TYPE_PER_DEPT: Final[dict[str, tuple[FocusType, ...]]] = {
    "Engineering": (
        FocusType.BALANCED,
        FocusType.QUALITY,
        FocusType.SPEED,
        FocusType.COST,
    ),
    "Sales": (
        FocusType.BALANCED,
        FocusType.AGGRESSIVE,
        FocusType.CONSERVATIVE,
        FocusType.RELATIONSHIP,
    ),
    "Operations": (
        FocusType.BALANCED,
        FocusType.EFFICIENCY,
        FocusType.SAFETY,
        FocusType.SCALE,
    ),
    "Marketing": (
        FocusType.BALANCED,
        FocusType.BRAND,
        FocusType.PERFORMANCE,
        FocusType.VIRAL,
    ),
    "Finance": (
        FocusType.BALANCED,
        FocusType.CONSERVATIVE_FIN,
        FocusType.GROWTH,
        FocusType.HEDGE,
    ),
}


DEFAULT_FOCUS: Final[FocusType] = FocusType.BALANCED


@dataclasses.dataclass(frozen=True, slots=True)
class FocusChoice:
    """Per-department focus snapshot stored on GameState (T40).

    Attributes:
        dept_id: Department this focus applies to (str at runtime;
            typeshells use ``DepartmentId``).
        focus: Selected ``FocusType``.
        set_tick: ``state.tick`` value when the focus was last changed.
            Used by T43 to enforce a 16-week cooldown between changes.
    """

    dept_id: str
    focus: FocusType
    set_tick: int

    def __post_init__(self) -> None:
        if isinstance(self.set_tick, bool) or not isinstance(self.set_tick, int):
            raise ValueError(f"set_tick must be a strict int, got {type(self.set_tick).__name__}")
        if self.set_tick < 0:
            raise ValueError(f"set_tick must be >= 0, got {self.set_tick!r}")
        if not isinstance(self.dept_id, str):
            raise ValueError(f"dept_id must be a str, got {type(self.dept_id).__name__}")
        # FocusType StrEnum membership is implicit via attribute access;
        # we accept any FocusType instance OR a string value.
        if not isinstance(self.focus, FocusType):
            # Allow string values that map to a valid FocusType.
            try:
                FocusType(self.focus)
            except ValueError as exc:
                raise ValueError(
                    f"focus must be a FocusType (or its string value), "
                    f"got {type(self.focus).__name__}: {self.focus!r}"
                ) from exc


def default_dept_focus() -> dict[str, FocusChoice]:
    """Return an empty dept_focus mapping for ``new_game``.

    Actual entries are created when a department is unlocked. For the
    canonical empty starting state (no departments), the map is empty.
    """
    return {}


__all__ = [
    "DEFAULT_FOCUS",
    "FOCUS_TYPE_PER_DEPT",
    "FocusChoice",
    "FocusType",
    "default_dept_focus",
]
