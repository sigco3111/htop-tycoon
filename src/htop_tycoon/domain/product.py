"""Domain: Product aggregate + lifecycle helpers (T6).

Pure data + pure lifecycle helpers. No market competition, pricing, or
competitor-interaction logic lives here — those live in ``engine/`` (T12+).
``Product`` is strictly frozen; updates happen via ``dataclasses.replace``.

Lifecycle model:
    The 4 stages (intro, growth, maturity, decline) have durations defined
    in ``balance.yaml`` under ``products.lifecycle_weeks``:

        intro    = 8   weeks
        growth   = 26  weeks
        maturity = 52  weeks
        decline  = 26  weeks
        ------------------------
        total    = 112 weeks

    ``advance_lifecycle_weeks`` accumulates weeks and transitions at stage
    boundaries. The decline stage is terminal: once the decline stage is
    fully consumed (``weeks_in_stage == decline_weeks``), further advance
    calls are no-ops and the product is frozen at ``stage=decline,
    weeks_in_stage=decline_weeks``. The engine (T12+) can detect
    "end of lifecycle" by checking ``weeks_in_stage >= decline_weeks`` on
    a product in the decline stage. See ``.omo/evidence/task-6-htop-tycoon.txt``
    for the design rationale.
"""

from __future__ import annotations

import dataclasses
from enum import Enum

from htop_tycoon.domain.state import ProductId

__all__ = [
    "LifecycleStage",
    "Product",
    "ProductType",
    "advance_lifecycle_weeks",
    "compute_revenue_per_week",
]


class ProductType(Enum):
    """The 3 locked product types.

    Locked at 3 by the plan ("Limit scope: no more than 3 products. Violations
    require plan revision"). Adding a fourth value requires a plan update first.
    """

    SaaS = "SaaS"
    Hardware = "Hardware"
    Consulting = "Consulting"


class LifecycleStage(Enum):
    """The 4 locked lifecycle stages of a product.

    Locked at 4 by the plan. Order is significant: ``advance_lifecycle_weeks``
    walks these in declaration order, so the members must remain in
    intro -> growth -> maturity -> decline sequence.
    """

    intro = "intro"
    growth = "growth"
    maturity = "maturity"
    decline = "decline"


# Canonical stage order. Used by ``advance_lifecycle_weeks`` to walk forward.
_STAGE_ORDER: tuple[LifecycleStage, ...] = (
    LifecycleStage.intro,
    LifecycleStage.growth,
    LifecycleStage.maturity,
    LifecycleStage.decline,
)

# Bounds: revenue must be non-negative (no debt-style negative revenue).
REVENUE_PER_WEEK_MIN: int = 0

# Market share bounds: closed interval [0.0, 1.0].
MARKET_SHARE_MIN: float = 0.0
MARKET_SHARE_MAX: float = 1.0

# Weeks in stage must be non-negative (the engine never rewinds time).
WEEKS_IN_STAGE_MIN: int = 0


def _require_strict_int(name: str, value: object) -> int:
    """Validate that ``value`` is a built-in ``int`` (rejecting ``bool`` and ``float``).

    ``bool`` is a subclass of ``int`` in Python; we reject it explicitly so
    ``True``/``False`` cannot silently sneak into numeric fields.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{name} must be a strict int, got {type(value).__name__}: {value!r}"
        )
    return value


def _validate_market_share(value: object) -> float:
    """Validate Product.market_share: numeric in [0.0, 1.0].

    Rejects bool, non-numeric, and out-of-range values. Accepts int (will be
    converted to float) and float.
    """
    if isinstance(value, bool):
        raise ValueError(
            f"market_share must be a number, got {type(value).__name__}: {value!r}"
        )
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"market_share must be a number, got {type(value).__name__}: {value!r}"
        )
    if not MARKET_SHARE_MIN <= float(value) <= MARKET_SHARE_MAX:
        raise ValueError(
            f"market_share must be in [{MARKET_SHARE_MIN}, {MARKET_SHARE_MAX}], "
            f"got {value!r}"
        )
    return float(value)


def _validate_weeks_in_stage(value: object) -> int:
    """Validate Product.weeks_in_stage: strict int, >= 0."""
    validated = _require_strict_int("weeks_in_stage", value)
    if validated < WEEKS_IN_STAGE_MIN:
        raise ValueError(
            f"weeks_in_stage must be >= {WEEKS_IN_STAGE_MIN}, got {validated!r}"
        )
    return validated


def _validate_revenue_per_week(value: object) -> int:
    """Validate Product.revenue_per_week: strict int, >= 0."""
    validated = _require_strict_int("revenue_per_week", value)
    if validated < REVENUE_PER_WEEK_MIN:
        raise ValueError(
            f"revenue_per_week must be >= {REVENUE_PER_WEEK_MIN}, got {validated!r}"
        )
    return validated


def _require_non_negative_n(n: object) -> int:
    """Validate that ``n`` is a strict int >= 0 (the ``advance`` step count)."""
    validated = _require_strict_int("n", n)
    if validated < 0:
        raise ValueError(f"n must be >= 0, got {validated!r}")
    return validated


@dataclasses.dataclass(frozen=True, slots=True)
class Product:
    """A product the company sells.

    Attributes:
        id: Stable identifier (e.g. ``"prod-saas-1"``).
        type: The product kind (SaaS / Hardware / Consulting).
        lifecycle: Current lifecycle stage.
        weeks_in_stage: Number of weeks spent in ``lifecycle`` (>= 0, strict int).
            At the stage boundary (== stage duration) the next ``advance`` call
            transitions to the next stage.
        market_share: This product's fraction of its market, in [0.0, 1.0].
        revenue_per_week: Cached revenue per week (non-negative strict int).
            Sourced from ``compute_revenue_per_week``; the engine refreshes this
            on every tick that affects revenue.
    """

    id: ProductId
    type: ProductType
    lifecycle: LifecycleStage
    weeks_in_stage: int
    market_share: float
    revenue_per_week: int

    def __post_init__(self) -> None:
        _validate_market_share(self.market_share)
        _validate_weeks_in_stage(self.weeks_in_stage)
        _validate_revenue_per_week(self.revenue_per_week)


def advance_lifecycle_weeks(
    product: Product,
    n: int,
    lifecycle_weeks: dict[str, int],
) -> Product:
    """Return a new ``Product`` advanced by ``n`` weeks through the lifecycle.

    Pure function. Does NOT mutate ``product``; uses ``dataclasses.replace`` to
    produce a new instance with the updated ``lifecycle`` and ``weeks_in_stage``
    fields. All other fields (``id``, ``type``, ``market_share``,
    ``revenue_per_week``) are preserved.

    Transition semantics:
        ``weeks_in_stage`` is the count of weeks spent in the current stage
        (0-indexed). When the next ``advance`` call would push the count past
        the current stage's duration, the product transitions to the next
        stage and the count resets to the overflow.

        The decline stage is terminal: once it is fully consumed, further
        advance calls are no-ops and the product is frozen at
        ``stage=decline, weeks_in_stage=decline_weeks``. The engine (T12+)
        can detect "end of lifecycle" via ``weeks_in_stage >= decline_weeks``
        on a product in the decline stage.

    Args:
        product: The product to advance. Not mutated.
        n: Number of weeks to advance. Must be a strict int >= 0.
        lifecycle_weeks: Map of stage name -> week duration. Keys must be
            ``"intro"``, ``"growth"``, ``"maturity"``, ``"decline"`` (the
            ``LifecycleStage`` member names). Typically sourced from
            ``balance.yaml`` via ``load_balance()["products"]["lifecycle_weeks"]``.

    Returns:
        A new ``Product`` with updated ``lifecycle`` and ``weeks_in_stage``.

    Raises:
        ValueError: If ``n`` is negative or non-int, or if any required stage
            key is missing from ``lifecycle_weeks``.
    """
    _require_non_negative_n(n)

    # n == 0: return a fresh instance with identical field values.
    if n == 0:
        return dataclasses.replace(product)

    # Resolve the current stage index. ``LifecycleStage`` is locked to 4 values
    # in the canonical intro->growth->maturity->decline order, so the index
    # lookup is total and safe.
    current_idx = _STAGE_ORDER.index(product.lifecycle)
    weeks = product.weeks_in_stage + n
    last_idx = len(_STAGE_ORDER) - 1

    # Walk forward through stages until the overflow fits the current stage.
    while current_idx < last_idx:
        current_stage = _STAGE_ORDER[current_idx]
        try:
            duration = lifecycle_weeks[current_stage.name]
        except KeyError as exc:
            raise KeyError(
                f"lifecycle_weeks is missing required stage key {current_stage.name!r}"
            ) from exc
        # ``weeks <= duration`` keeps ``weeks_in_stage == duration`` as the
        # valid boundary value before the next ``advance`` triggers a transition.
        if weeks <= duration:
            return dataclasses.replace(
                product,
                lifecycle=current_stage,
                weeks_in_stage=weeks,
            )
        weeks -= duration
        current_idx += 1

    # In the decline stage (last): freeze at decline_weeks. weeks may be
    # greater than decline_weeks (overflow), equal to it, or even less
    # (caller advanced by a small n from a near-boundary starting position);
    # in all cases the capped value is the documented end-of-life state.
    decline_stage = _STAGE_ORDER[last_idx]
    try:
        decline_weeks = lifecycle_weeks[decline_stage.name]
    except KeyError as exc:
        raise KeyError(
            f"lifecycle_weeks is missing required stage key {decline_stage.name!r}"
        ) from exc
    capped_weeks = min(weeks, decline_weeks)
    return dataclasses.replace(
        product,
        lifecycle=decline_stage,
        weeks_in_stage=capped_weeks,
    )


def compute_revenue_per_week(
    product: Product,
    total_skill: int,
    revenue_per_skill_point: int,
) -> int:
    """Return this product's weekly revenue as a strict int.

    Pure function. Formula::

        revenue = int(product.market_share * total_skill * revenue_per_skill_point)

    The result is truncated (``int()``), not rounded, so the function is
    deterministic and free of banker-rounding surprises. The engine (T12+)
    is expected to call this each tick and write the result back to
    ``product.revenue_per_week`` via ``dataclasses.replace``.

    Args:
        product: The product to compute revenue for. Only ``market_share`` is read.
        total_skill: The company's total skill points (sum of all employees' skill).
        revenue_per_skill_point: Per-skill-point weekly revenue multiplier. Typically
            sourced from ``balance.yaml`` ``products.revenue_per_skill_point_per_week``.

    Returns:
        The product's weekly revenue as a non-negative int (0 if any input is 0).
    """
    return int(product.market_share * total_skill * revenue_per_skill_point)
