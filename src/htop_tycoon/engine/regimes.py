"""Engine: Market regime types, modifier loader, and ``regime_step`` (Wave 7 / T36-T37).

Frozen dataclasses that describe how each regime modifies engine
sub-systems (revenue, salary growth, competitor aggression baseline,
event probability, cash shock probability). All numeric values come
from ``data/balance.yaml`` under ``regimes.*``; no magic numbers in
code. ``regime_step()`` advances the regime clock each tick and rolls a
per-tick cash shock for CRISIS.

Per AGENTS.md "Determinism" / "Event publishing":
- No ``random.*`` calls outside :class:`GameRNG`.
- No ``event_bus.publish`` calls. Cash-shock and regime-change events
  are returned in the result tuple; the caller (T16 App or T9 tick
  engine) publishes them via ``app_wiring``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any, Literal

from htop_tycoon.domain.regimes import RegimeState, RegimeType
from htop_tycoon.domain.state import GameState
from htop_tycoon.engine.events import Event
from htop_tycoon.engine.rng import GameRNG

# Locked ranges (T36). The engine integration in T38 may add a clamp at
# call-site for combined focus+regime multipliers, but the per-regime
# values themselves must already be inside these bounds.
_MULT_LOWER: float = 0.5
_MULT_UPPER: float = 2.0
_PROB_LOWER: float = 0.0
_PROB_UPPER: float = 1.0
_EPS_SUM: float = 1e-9


# ---------------------------------------------------------------------------
# Engine signals returned by ``regime_step`` (T37)
# ---------------------------------------------------------------------------

AlertSeverity = Literal["info", "warn", "alert"]


@dataclasses.dataclass(frozen=True, slots=True)
class RegimeChanged(Event):
    """Notification: the active regime transitioned ``prev`` -> ``next``.

    Inherits from ``Event`` so it can flow through the bus.

    Emitted by ``regime_step()`` exactly when the active cycle's
    ``max_weeks_in_regime`` boundary is crossed. The caller publishes
    this via EventBus; the event carries no state-mutation payload (the
    next state already reflects the transition).
    """

    kind: Literal["regime_changed"]
    prev: RegimeType
    next: RegimeType
    tick: int
    weeks_in_prev: int


@dataclasses.dataclass(frozen=True, slots=True)
class CashShockEvent(Event):
    """Notification: a CRISIS cash shock just deducted ``amount`` from cash.

    Inherits from ``Event`` so it can flow through the bus.

    ``amount`` is a negative int (deduction). Severity is always
    ``"alert"`` because cash shock is the most disruptive regime
    effect. Caller applies the cash deduction via the cash-flow engine
    and publishes a UI ``AlertRaised`` message for the player.
    """

    kind: Literal["cash_shock"]
    amount: int  # negative
    severity: AlertSeverity
    regime: RegimeType
    tick: int


# Union of engine signals emitted by regime_step (T37). Kept distinct
# from ``domain.event.Effect`` (which is the engine mutation contract);
# these are read-only notifications.
RegimeSignal = RegimeChanged | CashShockEvent


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


# ---------------------------------------------------------------------------
# regime_step — T37
# ---------------------------------------------------------------------------


def regime_step(
    state: GameState,
    rng: GameRNG,
    cycles: Mapping[RegimeType, RegimeCycleConfig],
    cash_shock_amount: int,
) -> tuple[GameState, list[RegimeSignal]]:
    """Advance the macro regime clock by one tick.

    Algorithm (locked T37 contract):

    1. ``weeks_in_regime += 1`` (NOTE: compare-after-increment vs the
       active cycle's ``max_weeks_in_regime``).
    2. If ``weeks_in_regime >= max_weeks_in_regime``, sample next
       regime via :meth:`GameRNG.weighted_choice` over the cycle's
       transition weights. Reset ``weeks_in_regime = 0`` and stamp
       ``started_tick = state.tick + 1``. Emit one :class:`RegimeChanged`
       signal.
    3. Independently, every tick: roll ``rng.event(probability)`` on
       the new (or unchanged) regime's ``cash_shock_probability``.
       On True, emit a :class:`CashShockEvent` with
       ``amount = -cash_shock_amount`` (a deduction).

    Pure: no in-place mutation of ``state``; no ``event_bus.publish``
    calls. The returned ``(state, events)`` lets the caller choose
    where and when to publish.

    Args:
        state: Current ``GameState``. Treated as read-only.
        rng: Seeded ``GameRNG`` for the deterministic transition +
            shock rolls.
        cycles: Per-regime :class:`RegimeCycleConfig` mapping. Usually
            pre-loaded once at startup via
            :func:`load_regimes_from_balance` and reused.
        cash_shock_amount: Positive int from
            ``balance["regimes"]["crisis_cash_shock_amount"]``; emitted
            events store it as ``-cash_shock_amount`` (a cash deduction).

    Returns:
        ``(new_state, signals)`` where ``new_state`` has ``tick + 1``
        and an updated ``regime`` field, and ``signals`` is the list of
        0-2 events emitted this tick.
    """
    if not isinstance(cash_shock_amount, int) or isinstance(cash_shock_amount, bool):
        raise ValueError(
            f"cash_shock_amount must be a strict int, got {type(cash_shock_amount).__name__}"
        )
    if cash_shock_amount < 0:
        raise ValueError(
            f"cash_shock_amount must be non-negative (sign-flipped), got {cash_shock_amount}"
        )

    current_regime_state = state.regime
    current_cycle = cycles[current_regime_state.current]

    # Step 1+2: increment weeks; transition on max boundary.
    weeks_after = current_regime_state.weeks_in_regime + 1
    new_tick = state.tick + 1
    signals: list[RegimeSignal] = []

    transitioning = weeks_after >= current_cycle.max_weeks_in_regime
    if transitioning:
        # Sample next regime via weighted choice on transition weights.
        regimes = list(current_cycle.transition.weights.keys())
        weights = list(current_cycle.transition.weights.values())
        next_regime: RegimeType = rng.weighted_choice(regimes, weights)
        new_regime_state = RegimeState(
            current=next_regime,
            weeks_in_regime=0,
            started_tick=new_tick,
        )
        signals.append(
            RegimeChanged(
                kind="regime_changed",
                prev=current_regime_state.current,
                next=next_regime,
                tick=new_tick,
                weeks_in_prev=weeks_after,
            )
        )
    else:
        new_regime_state = RegimeState(
            current=current_regime_state.current,
            weeks_in_regime=weeks_after,
            started_tick=current_regime_state.started_tick,
        )

    # Step 3: cash shock on the new regime's probability.
    new_cycle = cycles[new_regime_state.current]
    if rng.event(new_cycle.modifiers.cash_shock_probability):
        signals.append(
            CashShockEvent(
                kind="cash_shock",
                amount=-cash_shock_amount,
                severity="alert",
                regime=new_regime_state.current,
                tick=new_tick,
            )
        )

    new_state = dataclasses.replace(state, regime=new_regime_state, tick=new_tick)
    return new_state, signals


__all__ = [
    "AlertSeverity",
    "CashShockEvent",
    "RegimeChanged",
    "RegimeCycleConfig",
    "RegimeModifiers",
    "RegimeSignal",
    "TransitionWeights",
    "load_regimes_from_balance",
    "regime_step",
]
