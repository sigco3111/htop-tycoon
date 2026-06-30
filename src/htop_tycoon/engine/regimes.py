"""Engine: Market regime modifier types (Wave 7 / T36).

Frozen dataclasses that describe how each regime modifies engine
sub-systems (revenue, salary growth, competitor aggression baseline,
event probability, cash shock probability). All numeric values come
from ``data/balance.yaml`` under ``regimes.*``; no magic numbers in
code.

Per AGENTS.md "Determinism" / "Event publishing":
- No RNG calls in this module.
- No ``event_bus.publish`` calls. (Cash-shock events are returned by
  ``regime_step()`` in T37, not published from here.)
- These types are loaded from balance once, then passed by value into
  the engine integration sites (T38) and ``regime_step`` (T37).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from htop_tycoon.domain.regimes import RegimeType

# Locked ranges (T36). The engine integration in T38 may add a clamp at
# call-site for combined focus+regime multipliers, but the per-regime
# values themselves must already be inside these bounds.
_MULT_LOWER: float = 0.5
_MULT_UPPER: float = 2.0
_PROB_LOWER: float = 0.0
_PROB_UPPER: float = 1.0
_EPS_SUM: float = 1e-9


def _coerce_regime_key(key: Any, *, where: str) -> RegimeType:
    """Convert a dict-key to ``RegimeType``. Accepts enum OR string.

    Because ``RegimeType`` is a ``StrEnum`` with values equal to names
    (``BOOM.value == "BOOM"``), a single ``RegimeType(key)`` lookup
    handles both cases.
    """
    if isinstance(key, RegimeType):
        return key
    if isinstance(key, str):
        try:
            return RegimeType(key)
        except ValueError:
            raise ValueError(
                f"{where}: unknown regime name {key!r}; valid: {[r.name for r in RegimeType]}"
            ) from None
    raise ValueError(f"{where}: keys must be RegimeType or str, got {type(key).__name__}: {key!r}")


def _validate_modifier_mult(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}: {value!r}")
    if not _MULT_LOWER <= float(value) <= _MULT_UPPER:
        raise ValueError(f"{name} must be in [{_MULT_LOWER}, {_MULT_UPPER}], got {value!r}")


def _validate_modifier_prob(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}: {value!r}")
    if not _PROB_LOWER <= float(value) <= _PROB_UPPER:
        raise ValueError(f"{name} must be in [{_PROB_LOWER}, {_PROB_UPPER}], got {value!r}")


@dataclasses.dataclass(frozen=True, slots=True)
class RegimeModifiers:
    """Five multipliers that govern how ``regime.current`` affects engine.

    Ranges are validated in ``__post_init__``:
        * ``revenue_multiplier``, ``salary_growth_multiplier``,
          ``event_probability_scale``: [0.5, 2.0]
        * ``competitor_aggression_baseline``, ``cash_shock_probability``:
          [0.0, 1.0]
    """

    revenue_multiplier: float
    salary_growth_multiplier: float
    competitor_aggression_baseline: float
    event_probability_scale: float
    cash_shock_probability: float

    def __post_init__(self) -> None:
        _validate_modifier_mult("revenue_multiplier", self.revenue_multiplier)
        _validate_modifier_mult("salary_growth_multiplier", self.salary_growth_multiplier)
        _validate_modifier_mult("event_probability_scale", self.event_probability_scale)
        _validate_modifier_prob(
            "competitor_aggression_baseline", self.competitor_aggression_baseline
        )
        _validate_modifier_prob("cash_shock_probability", self.cash_shock_probability)


@dataclasses.dataclass(frozen=True, slots=True)
class TransitionWeights:
    """Mapping of next-regime -> probability.

    Keys may be ``RegimeType`` enum members or strings (e.g., ``"BOOM"``);
    the latter are coerced via :func:`_coerce_regime_key`. All
    probabilities must sum to ``1.0`` (within ``1e-9`` epsilon); zero or
    negative weights are rejected.
    """

    weights: Mapping[Any, float]

    def __post_init__(self) -> None:
        coerced: dict[RegimeType, float] = {}
        for raw_key, v in self.weights.items():
            regime = _coerce_regime_key(raw_key, where="TransitionWeights")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(
                    f"weights must be numeric, got {raw_key!r}: {v!r} ({type(v).__name__})"
                )
            if float(v) < 0.0:
                raise ValueError(f"weights must be non-negative, got {raw_key!r}: {v!r}")
            coerced[regime] = float(v)
        # Re-bind to the coerced mapping via object.__setattr__ (we're
        # frozen but __post_init__ runs before freezing completes).
        object.__setattr__(self, "weights", coerced)
        total = float(sum(self.weights.values()))
        if not (1.0 - _EPS_SUM <= total <= 1.0 + _EPS_SUM):
            raise ValueError(
                f"transition weights must sum to 1.0 (epsilon={_EPS_SUM}), got total={total!r}"
            )


@dataclasses.dataclass(frozen=True, slots=True)
class RegimeCycleConfig:
    """Per-regime cycle configuration: min/max weeks + transition + modifiers.

    Used both at startup (loading ``balance.yaml``) and at runtime (T37
    ``regime_step`` consults the active cycle's ``min/max_weeks_in_regime``
    and ``transition`` to decide when and where to switch regimes).
    """

    type: Any  # RegimeType or str; coerced to RegimeType in __post_init__
    min_weeks_in_regime: int
    max_weeks_in_regime: int
    transition: TransitionWeights
    modifiers: RegimeModifiers

    def __post_init__(self) -> None:
        coerced = _coerce_regime_key(self.type, where="RegimeCycleConfig.type")
        if coerced is not self.type:
            object.__setattr__(self, "type", coerced)
        if not isinstance(self.min_weeks_in_regime, int) or isinstance(
            self.min_weeks_in_regime, bool
        ):
            raise ValueError(
                "min_weeks_in_regime must be a strict int, got "
                f"{type(self.min_weeks_in_regime).__name__}"
            )
        if not isinstance(self.max_weeks_in_regime, int) or isinstance(
            self.max_weeks_in_regime, bool
        ):
            raise ValueError(
                "max_weeks_in_regime must be a strict int, got "
                f"{type(self.max_weeks_in_regime).__name__}"
            )
        if self.min_weeks_in_regime < 1:
            raise ValueError(f"min_weeks_in_regime must be >= 1, got {self.min_weeks_in_regime!r}")
        if self.max_weeks_in_regime < self.min_weeks_in_regime:
            raise ValueError(
                f"max_weeks_in_regime ({self.max_weeks_in_regime}) must be >= "
                f"min_weeks_in_regime ({self.min_weeks_in_regime})"
            )


def load_regimes_from_balance(
    balance: Mapping[str, object],
) -> Mapping[RegimeType, RegimeCycleConfig]:
    """Parse ``balance["regimes"]["cycles"]`` into a typed mapping.

    Each cycle config in YAML must contain ``min_weeks``, ``max_weeks``,
    ``transition`` (a dict keyed by regime name), AND ``modifiers``
    (the per-regime multiplier set). The function returns a dictionary
    keyed by :class:`RegimeType`.

    Pure: no side effects.

    Raises:
        KeyError: If any required sub-key is absent.
        TypeError: Propagated from the typed dataclass constructors.
    """
    cycles_raw = balance["regimes"]["cycles"]  # type: ignore[index]
    if not isinstance(cycles_raw, Mapping):
        raise TypeError(f"regimes.cycles must be a mapping, got {type(cycles_raw).__name__}")
    out: dict[RegimeType, RegimeCycleConfig] = {}
    for regime_name, cfg_raw in cycles_raw.items():
        if not isinstance(cfg_raw, Mapping):
            raise TypeError(f"cycles.{regime_name} must be a mapping, got {type(cfg_raw).__name__}")
        # ``modifiers`` is required at the cycle level (T36 design —
        # per-regime knobs live next to their cycle so a single YAML
        # block is grep-able).
        if "modifiers" not in cfg_raw:
            raise KeyError(f"regimes.cycles.{regime_name}: missing required key 'modifiers'")
        modifiers_raw = cfg_raw["modifiers"]
        if not isinstance(modifiers_raw, Mapping):
            raise TypeError(f"cycles.{regime_name}.modifiers must be a mapping")
        transition_weights_raw = cfg_raw["transition"]
        transition_weights_dict = {k: float(v) for k, v in transition_weights_raw.items()}
        cfg = RegimeCycleConfig(
            type=regime_name,
            min_weeks_in_regime=int(cfg_raw["min_weeks"]),
            max_weeks_in_regime=int(cfg_raw["max_weeks"]),
            transition=TransitionWeights(weights=transition_weights_dict),
            modifiers=RegimeModifiers(
                revenue_multiplier=float(modifiers_raw["revenue_multiplier"]),
                salary_growth_multiplier=float(modifiers_raw["salary_growth_multiplier"]),
                competitor_aggression_baseline=float(
                    modifiers_raw["competitor_aggression_baseline"]
                ),
                event_probability_scale=float(modifiers_raw["event_probability_scale"]),
                cash_shock_probability=float(modifiers_raw["cash_shock_probability"]),
            ),
        )
        out[cfg.type] = cfg
    return out


__all__ = [
    "RegimeCycleConfig",
    "RegimeModifiers",
    "TransitionWeights",
    "load_regimes_from_balance",
]
