"""Tests for T4: domain.state (GameState aggregate, Company, serialization).

Locks the contract: GameState is frozen, state_hash is deterministic, Company
rejects invalid market_cap, new_game uses balance.yaml starting_cash.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.domain.state import (
    Company,
    GameTime,
    new_game,
    state_hash,
)

# -- Company -----------------------------------------------------------------


def test_company_rejects_negative_market_cap() -> None:
    """Company.market_cap must be non-negative."""
    with pytest.raises(ValueError, match="market_cap"):
        Company(id="c1", name="Acme", cash=50_000, market_cap=-1)


def test_company_rejects_non_int_market_cap() -> None:
    """Company.market_cap must be int (not bool, not float)."""
    with pytest.raises(ValueError, match="market_cap"):
        Company(id="c1", name="Acme", cash=50_000, market_cap=1.5)  # type: ignore[arg-type]


def test_company_rejects_bool_market_cap() -> None:
    """bool is a subclass of int in Python; we still reject it explicitly."""
    with pytest.raises(ValueError, match="market_cap"):
        Company(id="c1", name="Acme", cash=50_000, market_cap=True)  # type: ignore[arg-type]


def test_company_accepts_zero_market_cap() -> None:
    """market_cap=0 is the boundary; must be allowed (newly-founded company)."""
    c = Company(id="c1", name="Acme", cash=50_000, market_cap=0)
    assert c.market_cap == 0


def test_company_is_frozen() -> None:
    """Company must be a frozen dataclass."""
    c = Company(id="c1", name="Acme", cash=50_000, market_cap=0)
    with pytest.raises(FrozenInstanceError):
        c.cash = 1  # type: ignore[misc]


# -- GameTime ----------------------------------------------------------------


def test_game_time_validates_week_lower_bound() -> None:
    """week must be in [1, 52]."""
    with pytest.raises(ValueError, match="week"):
        GameTime(year=1, quarter=1, week=0)


def test_game_time_validates_week_upper_bound() -> None:
    """week must be in [1, 52]."""
    with pytest.raises(ValueError, match="week"):
        GameTime(year=1, quarter=1, week=53)


def test_game_time_validates_quarter_lower_bound() -> None:
    """quarter must be in [1, 4]."""
    with pytest.raises(ValueError, match="quarter"):
        GameTime(year=1, quarter=0, week=1)


def test_game_time_validates_quarter_upper_bound() -> None:
    """quarter must be in [1, 4]."""
    with pytest.raises(ValueError, match="quarter"):
        GameTime(year=1, quarter=5, week=1)


def test_game_time_is_frozen() -> None:
    """GameTime must be a frozen dataclass."""
    t = GameTime(year=1, quarter=1, week=1)
    with pytest.raises(FrozenInstanceError):
        t.week = 2  # type: ignore[misc]


# -- new_game ----------------------------------------------------------------


def test_new_game_seed_42_defaults() -> None:
    """new_game(seed=42) returns tick=0, week=1, secret_investor_cleared=False."""
    s = new_game(42)
    assert s.tick == 0
    assert s.game_time.week == 1
    assert s.game_time.quarter == 1
    assert s.game_time.year == 1
    assert s.secret_investor_cleared is False
    assert s.rng_seed == 42
    assert s.version == 1


def test_new_game_cash_comes_from_balance_yaml() -> None:
    """Company.cash is sourced from balance.yaml money.starting_cash (50_000)."""
    s = new_game(42)
    assert s.company.cash == 50_000


def test_new_game_initial_market_cap_equals_cash() -> None:
    """With no products, market_cap == cash on day 0."""
    s = new_game(42)
    assert s.company.market_cap == s.company.cash


def test_new_game_empty_collections() -> None:
    """Departments/employees/products/competitors start empty; events/ending_history too."""
    s = new_game(42)
    assert s.departments == {}
    assert s.employees == {}
    assert s.products == {}
    assert s.competitors == {}
    assert s.events_active == []
    assert s.ending_history == []


def test_new_game_company_has_id_and_name() -> None:
    """Company must have non-empty id and name."""
    s = new_game(42)
    assert s.company.id
    assert s.company.name
    assert isinstance(s.company.id, str)
    assert isinstance(s.company.name, str)


# -- Frozen GameState --------------------------------------------------------


def test_game_state_is_frozen() -> None:
    """Mutating state.tick must raise FrozenInstanceError."""
    s = new_game(42)
    with pytest.raises(FrozenInstanceError):
        s.tick = 5  # type: ignore[misc]


def test_game_state_dataclasses_replace_works() -> None:
    """Updates are made via dataclasses.replace, not mutation."""
    s = new_game(42)
    s2 = dataclasses.replace(s, tick=5)
    assert s.tick == 0  # original unchanged
    assert s2.tick == 5
    assert s2.rng_seed == s.rng_seed  # other fields preserved


# -- state_hash --------------------------------------------------------------


def test_state_hash_is_deterministic() -> None:
    """Same seed -> same hash, repeatedly."""
    s1 = new_game(42)
    s2 = new_game(42)
    assert state_hash(s1) == state_hash(s2)


def test_state_hash_different_seeds_differ() -> None:
    """Different seeds -> different hashes (sanity: the seed actually affects state)."""
    s1 = new_game(42)
    s2 = new_game(43)
    assert state_hash(s1) != state_hash(s2)


def test_state_hash_is_sha256_hex() -> None:
    """state_hash returns a 64-char lowercase hex string (SHA-256 digest)."""
    s = new_game(42)
    h = state_hash(s)
    assert isinstance(h, str)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_state_hash_uses_canonical_sha256() -> None:
    """state_hash must be SHA-256 of json.dumps(asdict(state), sort_keys=True, default=str)."""
    s = new_game(42)
    payload = json.dumps(dataclasses.asdict(s), sort_keys=True, default=str).encode()
    expected = hashlib.sha256(payload).hexdigest()
    assert state_hash(s) == expected


def test_state_hash_changes_after_replace() -> None:
    """Changing tick must change the hash (proves the hash reflects state content)."""
    s = new_game(42)
    h_before = state_hash(s)
    s2 = dataclasses.replace(s, tick=1)
    h_after = state_hash(s2)
    assert h_before != h_after
