"""Tests for T7: domain.market (Competitor + Market + load_default_market).

Locks the contract:
- Competitor validates market_share in [0.0, 1.0], aggression in [0.0, 1.0],
  cash >= 0; is frozen.
- Market enforces sum(competitor.market_share) <= 1.0 invariant; is frozen.
- load_default_market(balance) returns a Market with the 3 spec-named
  competitors whose aggression values fall in [0.3, 0.6].
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.market import Competitor, Market, load_default_market
from htop_tycoon.domain.state import CompetitorId


def _cid(name: str) -> CompetitorId:
    """Helper: cast a plain str to CompetitorId."""
    return CompetitorId(name)


def _make_competitor(
    name: str,
    share: float = 0.1,
    aggression: float = 0.5,
    cash: int = 1_000,
    alive: bool = True,
) -> Competitor:
    return Competitor(
        id=_cid(name),
        name=name,
        market_share=share,
        aggression=aggression,
        cash=cash,
        alive=alive,
    )


# -- Competitor construction & field round-trip -----------------------------


def test_competitor_constructs_with_valid_values() -> None:
    """All six fields round-trip from the constructor."""
    c = Competitor(
        id=_cid("incumbents-co"),
        name="Incumbents-Co",
        market_share=0.30,
        aggression=0.6,
        cash=50_000,
        alive=True,
    )
    assert c.id == _cid("incumbents-co")
    assert c.name == "Incumbents-Co"
    assert c.market_share == 0.30
    assert c.aggression == 0.6
    assert c.cash == 50_000
    assert c.alive is True


def test_competitor_alive_defaults_to_true() -> None:
    """alive defaults to True when omitted."""
    c = Competitor(
        id=_cid("x"),
        name="X",
        market_share=0.1,
        aggression=0.5,
        cash=0,
    )
    assert c.alive is True


# -- Competitor: market_share validation -------------------------------------


def test_competitor_rejects_market_share_above_one() -> None:
    """market_share > 1.0 raises ValueError."""
    with pytest.raises(ValueError, match="market_share"):
        Competitor(
            id=_cid("x"),
            name="X",
            market_share=1.5,
            aggression=0.5,
            cash=0,
        )


def test_competitor_rejects_negative_market_share() -> None:
    """market_share < 0.0 raises ValueError (matches plan QA scenario)."""
    with pytest.raises(ValueError, match="market_share"):
        Competitor(
            id=_cid("x"),
            name="X",
            market_share=-0.1,
            aggression=0.5,
            cash=0,
        )


def test_competitor_accepts_market_share_zero_boundary() -> None:
    """market_share == 0.0 is the lower boundary; must be accepted."""
    c = Competitor(
        id=_cid("x"),
        name="X",
        market_share=0.0,
        aggression=0.5,
        cash=0,
    )
    assert c.market_share == 0.0


def test_competitor_accepts_market_share_one_boundary() -> None:
    """market_share == 1.0 is the upper boundary; must be accepted."""
    c = Competitor(
        id=_cid("x"),
        name="X",
        market_share=1.0,
        aggression=0.5,
        cash=0,
    )
    assert c.market_share == 1.0


# -- Competitor: aggression validation ----------------------------------------


def test_competitor_rejects_aggression_above_one() -> None:
    """aggression > 1.0 raises ValueError (matches plan QA scenario)."""
    with pytest.raises(ValueError, match="aggression"):
        Competitor(
            id=_cid("x"),
            name="X",
            market_share=0.1,
            aggression=1.5,
            cash=0,
        )


def test_competitor_rejects_negative_aggression() -> None:
    """aggression < 0.0 raises ValueError."""
    with pytest.raises(ValueError, match="aggression"):
        Competitor(
            id=_cid("x"),
            name="X",
            market_share=0.1,
            aggression=-0.1,
            cash=0,
        )


def test_competitor_accepts_aggression_zero_boundary() -> None:
    """aggression == 0.0 is the lower boundary; must be accepted."""
    c = Competitor(
        id=_cid("x"),
        name="X",
        market_share=0.1,
        aggression=0.0,
        cash=0,
    )
    assert c.aggression == 0.0


def test_competitor_accepts_aggression_one_boundary() -> None:
    """aggression == 1.0 is the upper boundary; must be accepted."""
    c = Competitor(
        id=_cid("x"),
        name="X",
        market_share=0.1,
        aggression=1.0,
        cash=0,
    )
    assert c.aggression == 1.0


# -- Competitor: cash validation ----------------------------------------------


def test_competitor_rejects_negative_cash() -> None:
    """cash < 0 raises ValueError."""
    with pytest.raises(ValueError, match="cash"):
        Competitor(
            id=_cid("x"),
            name="X",
            market_share=0.1,
            aggression=0.5,
            cash=-1,
        )


def test_competitor_accepts_zero_cash() -> None:
    """cash == 0 is the lower boundary; must be accepted."""
    c = Competitor(
        id=_cid("x"),
        name="X",
        market_share=0.1,
        aggression=0.5,
        cash=0,
    )
    assert c.cash == 0


# -- Competitor: frozenness --------------------------------------------------


def test_competitor_is_frozen() -> None:
    """Competitor must be a frozen dataclass (no field mutation)."""
    c = _make_competitor("x")
    with pytest.raises(FrozenInstanceError):
        c.cash = 100  # type: ignore[misc]


# -- Market: invariants ------------------------------------------------------


def test_market_rejects_share_sum_above_one() -> None:
    """Market with sum(market_share) > 1.0 raises ValueError.

    Mirrors the plan's invariant: ``sum(c.market_share for c in
    competitors.values()) <= 1.0``.
    """
    competitors = {
        _cid("a"): _make_competitor("a", share=0.6),
        _cid("b"): _make_competitor("b", share=0.5),
    }
    with pytest.raises(ValueError, match="market_share"):
        Market(competitors=competitors, total_demand_per_week=1_000)


def test_market_accepts_share_sum_exactly_one() -> None:
    """sum == 1.0 is the boundary; must be accepted."""
    competitors = {
        _cid("a"): _make_competitor("a", share=0.6),
        _cid("b"): _make_competitor("b", share=0.4),
    }
    market = Market(competitors=competitors, total_demand_per_week=1_000)
    assert sum(c.market_share for c in market.competitors.values()) == 1.0
    assert market.total_demand_per_week == 1_000


def test_market_accepts_share_sum_well_below_one() -> None:
    """sum << 1.0 must be accepted (leaves headroom for the player)."""
    competitors = {
        _cid("a"): _make_competitor("a", share=0.3),
        _cid("b"): _make_competitor("b", share=0.2),
    }
    market = Market(competitors=competitors, total_demand_per_week=5_000)
    assert market.total_demand_per_week == 5_000


def test_market_accepts_empty_competitors() -> None:
    """Empty competitors dict is valid (sum = 0 <= 1.0)."""
    market = Market(competitors={}, total_demand_per_week=1_000)
    assert market.competitors == {}
    assert market.total_demand_per_week == 1_000


def test_market_is_frozen() -> None:
    """Market must be a frozen dataclass."""
    competitors = {_cid("a"): _make_competitor("a", share=0.3)}
    market = Market(competitors=competitors, total_demand_per_week=1_000)
    with pytest.raises(FrozenInstanceError):
        market.total_demand_per_week = 500  # type: ignore[misc]


# -- load_default_market -----------------------------------------------------


def test_load_default_market_returns_three_competitors() -> None:
    """load_default_market(load_balance()) yields exactly 3 Competitor entries."""
    market = load_default_market(load_balance())
    assert len(market.competitors) == 3


def test_load_default_market_aggression_in_spec_range() -> None:
    """All default competitor aggression values lie in [0.3, 0.6].

    Matches the plan's QA scenario: 'load default market → 3 competitors
    with aggression in [0.3, 0.6]'.
    """
    market = load_default_market(load_balance())
    for comp in market.competitors.values():
        assert 0.3 <= comp.aggression <= 0.6, (
            f"{comp.name} aggression {comp.aggression} out of [0.3, 0.6]"
        )


def test_load_default_market_competitor_names_match_spec() -> None:
    """The 3 default competitors must be the spec names verbatim."""
    market = load_default_market(load_balance())
    names = {c.name for c in market.competitors.values()}
    assert names == {"Incumbents-Co", "Disruptors-Inc", "Foreign-LLC"}


def test_load_default_market_aggression_values_match_plan() -> None:
    """Aggression values per plan section T7: Incumbents-Co=0.6,
    Disruptors-Inc=0.4, Foreign-LLC=0.3."""
    market = load_default_market(load_balance())
    by_name = {c.name: c.aggression for c in market.competitors.values()}
    assert by_name["Incumbents-Co"] == 0.6
    assert by_name["Disruptors-Inc"] == 0.4
    assert by_name["Foreign-LLC"] == 0.3


def test_load_default_market_share_sum_satisfies_invariant() -> None:
    """Default market sum(market_share) must satisfy the <= 1.0 invariant."""
    market = load_default_market(load_balance())
    total = sum(c.market_share for c in market.competitors.values())
    assert 0.0 <= total <= 1.0


def test_load_default_market_has_positive_total_demand() -> None:
    """total_demand_per_week must be a positive integer."""
    market = load_default_market(load_balance())
    assert isinstance(market.total_demand_per_week, int)
    assert market.total_demand_per_week > 0


def test_load_default_market_uses_balance_starting_list() -> None:
    """Competitor names come from balance["competitors"]["starting"]."""
    balance = load_balance()
    starting_names = set(balance["competitors"]["starting"])
    market = load_default_market(balance)
    actual_names = {c.name for c in market.competitors.values()}
    assert starting_names == actual_names


def test_load_default_market_competitors_are_alive() -> None:
    """All default competitors must start alive=True."""
    market = load_default_market(load_balance())
    for comp in market.competitors.values():
        assert comp.alive is True


def test_load_default_market_is_frozen() -> None:
    """Market returned from load_default_market must be frozen."""
    market = load_default_market(load_balance())
    with pytest.raises(FrozenInstanceError):
        market.total_demand_per_week = 999  # type: ignore[misc]
