"""Domain: Market aggregate and Competitor model.

Pure data only. The market is the snapshot of all rival companies and the
total weekly demand; AI decision logic lives in ``engine/competitor_ai.py``
(T13) and consumes this structure but never mutates it.

The aggression and market_share values for the 3 default competitors are
baked in here, NOT in ``balance.yaml``, because the plan treats these
specific numbers as deliberate gameplay tuning (section T7). ``balance.yaml``
still owns derived game constants (action costs, aggression default fallback,
max aggression) and is consulted via ``load_balance()`` when needed.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from htop_tycoon.domain.state import CompetitorId

__all__ = ["Competitor", "Market", "load_default_market"]


# Default aggression per the plan (T7 QA scenario). Verbatim from the spec:
# Incumbents-Co=0.6, Disruptors-Inc=0.4, Foreign-LLC=0.3.
_DEFAULT_AGGRESSION: dict[str, float] = {
    "Incumbents-Co": 0.6,
    "Disruptors-Inc": 0.4,
    "Foreign-LLC": 0.3,
}

# Default market_share for the 3 starting competitors. Sum = 0.55, leaving
# 0.45 of the addressable market for the player to capture. NOT in balance.yaml
# because these are the canonical seed values; changing them is a gameplay
# decision, not a balance tuning.
_DEFAULT_MARKET_SHARE: dict[str, float] = {
    "Incumbents-Co": 0.30,
    "Disruptors-Inc": 0.15,
    "Foreign-LLC": 0.10,
}

# Initial cash for each competitor at game start. Same magnitude as the
# player's starting_cash (50_000 from balance.yaml) so no competitor is
# bankrupt on day 0.
_DEFAULT_COMPETITOR_STARTING_CASH: int = 50_000

# Total weekly demand for the MVP market. Fits comfortably inside
# balance.yaml's money.target_revenue=200_000 / 52 weeks ~ 3_846 per week,
# leaving headroom for the company's own product revenue.
_DEFAULT_TOTAL_DEMAND_PER_WEEK: int = 10_000


def _validate_unit_interval(name: str, value: object) -> float:
    """Validate ``value`` is a real number in [0.0, 1.0].

    Rejects ``bool`` (a subclass of ``int`` in Python) explicitly so
    ``True``/``False`` cannot silently sneak into share/aggression fields.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"{name} must be a number in [0.0, 1.0], "
            f"got {type(value).__name__}: {value!r}"
        )
    as_float = float(value)
    if not 0.0 <= as_float <= 1.0:
        raise ValueError(f"{name} must be in [0.0, 1.0], got {as_float!r}")
    return as_float


def _validate_non_negative_cash(value: object) -> int:
    """Validate ``value`` is a strict non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"cash must be a strict int, got {type(value).__name__}: {value!r}"
        )
    if value < 0:
        raise ValueError(f"cash must be non-negative, got {value!r}")
    return value


@dataclasses.dataclass(frozen=True, slots=True)
class Competitor:
    """A rival company competing for market share.

    Attributes:
        id: Stable identifier (``CompetitorId`` newtype around ``str``).
        name: Display name (Korean or English; no formatting here).
        market_share: Fraction of total weekly demand captured. In [0.0, 1.0].
        aggression: Strategic aggressiveness in [0.0, 1.0]. Used by the
            engine to weight AI action selection; 0 is passive, 1 is
            maximally aggressive. Not consumed in this module.
        cash: Operating cash on hand. Must be non-negative.
        alive: Whether the competitor is still operating. Defaults to True.
            Engine flips this to False when a competitor is acquired, exits,
            or otherwise leaves the market.
    """

    id: CompetitorId
    name: str
    market_share: float
    aggression: float
    cash: int
    alive: bool = True

    def __post_init__(self) -> None:
        _validate_unit_interval("market_share", self.market_share)
        _validate_unit_interval("aggression", self.aggression)
        _validate_non_negative_cash(self.cash)


@dataclasses.dataclass(frozen=True, slots=True)
class Market:
    """The market aggregate: all competitors + total weekly demand.

    Invariant: ``sum(c.market_share for c in competitors.values()) <= 1.0``.
    The remainder is the player's addressable share.
    """

    competitors: dict[CompetitorId, Competitor]
    total_demand_per_week: int

    def __post_init__(self) -> None:
        total = sum(c.market_share for c in self.competitors.values())
        if total > 1.0:
            raise ValueError(
                f"sum(competitor.market_share) must be <= 1.0, got {total!r}"
            )


def load_default_market(balance: dict[str, Any]) -> Market:
    """Build the default 3-competitor market from a parsed ``balance.yaml`` dict.

    Competitor names come from ``balance["competitors"]["starting"]``.
    Aggression and market_share values come from the module's
    ``_DEFAULT_AGGRESSION`` / ``_DEFAULT_MARKET_SHARE`` tables (per the plan
    section T7). Total weekly demand is fixed at ``_DEFAULT_TOTAL_DEMAND_PER_WEEK``.

    Args:
        balance: Parsed ``balance.yaml`` mapping. Must contain
            ``competitors.starting`` as a list of the 3 spec competitor names
            (``Incumbents-Co``, ``Disruptors-Inc``, ``Foreign-LLC``).

    Returns:
        A ``Market`` with 3 ``Competitor`` entries, each alive=True.

    Raises:
        KeyError: If ``balance["competitors"]["starting"]`` is missing OR if a
            name in that list has no entry in the default aggression/share
            tables (fail-loud policy).
    """
    starting_names: list[str] = list(balance["competitors"]["starting"])
    competitors: dict[CompetitorId, Competitor] = {}
    for name in starting_names:
        competitors[CompetitorId(name)] = Competitor(
            id=CompetitorId(name),
            name=name,
            market_share=_DEFAULT_MARKET_SHARE[name],
            aggression=_DEFAULT_AGGRESSION[name],
            cash=_DEFAULT_COMPETITOR_STARTING_CASH,
        )
    return Market(
        competitors=competitors,
        total_demand_per_week=_DEFAULT_TOTAL_DEMAND_PER_WEEK,
    )
