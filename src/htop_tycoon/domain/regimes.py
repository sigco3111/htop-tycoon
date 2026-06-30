"""Domain: RegimeType enum + RegimeState dataclass (Wave 7 / T36).

These types are part of :class:`GameState` and are pure data. Engine
logic (regime stepping, modifier application) lives in
``engine.regimes``.

Per AGENTS.md "Determinism" / "State boundary":
- No random sources here.
- No ``event_bus.publish`` calls.
- These types travel through ``dataclasses.replace`` only.
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum
from typing import Final, TypeVar

T = TypeVar("T")


def _require_strict_nonneg_int(name: str, value: object) -> int:
    """Reject ``bool`` and ``float``; require the value to be ``int >= 0``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{name} must be a strict int, got {type(value).__name__}: {value!r}"
        )
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")
    return value


class RegimeType(StrEnum):
    """Macroeconomic state of the game world (T36).

    Transitions between regimes are driven by ``engine.regimes.regime_step``
    (T37). Inheriting from ``StrEnum`` (Python 3.11+) makes the enum's
    value equal its name, which keeps YAML keys (e.g., ``BOOM``) and
    enum members in lock-step and lets ``json.dumps`` round-trip without
    coercers.
    """

    BOOM = "BOOM"
    NORMAL = "NORMAL"
    RECESSION = "RECESSION"
    CRISIS = "CRISIS"


DEFAULT_REGIME_TYPE: Final[RegimeType] = RegimeType.NORMAL


@dataclasses.dataclass(frozen=True, slots=True)
class RegimeState:
    """Per-game macro regime snapshot stored on GameState (T36).

    Attributes:
        current: Active regime type.
        weeks_in_regime: How many in-game weeks the current regime has lasted.
        started_tick: ``state.tick`` value when the current regime began.
            Must be non-negative.
    """

    current: RegimeType
    weeks_in_regime: int
    started_tick: int

    def __post_init__(self) -> None:
        _require_strict_nonneg_int("weeks_in_regime", self.weeks_in_regime)
        _require_strict_nonneg_int("started_tick", self.started_tick)
        if not isinstance(self.current, RegimeType):
            raise ValueError(
                f"current must be a RegimeType, got {type(self.current).__name__}"
            )


def default_regime_state() -> RegimeState:
    """Return the initial :class:`RegimeState` for ``new_game``.

    Centralised here so ``domain.state.new_game`` and any future factory
    helpers (T32 frozen playthrough fixtures, T33 seeded games) all
    converge on the same default.
    """
    return RegimeState(
        current=DEFAULT_REGIME_TYPE,
        weeks_in_regime=0,
        started_tick=0,
    )


__all__ = [
    "DEFAULT_REGIME_TYPE",
    "RegimeState",
    "RegimeType",
    "default_regime_state",
]
