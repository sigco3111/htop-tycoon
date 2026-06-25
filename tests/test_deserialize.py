"""Tests for T28: ``deserialize()`` — JSON to GameState + corruption recovery.

Locks the contract for the in-memory deserializer:

- ``deserialize(data)`` converts a v1 envelope (``{"version": 1, "state": ...,
  "saved_at_iso": ...}``) back into a :class:`GameState`. The round-trip
  preserves ``state_hash`` for any state ``serialize`` produced.
- ``deserialize`` NEVER raises on corruption. Three corruption modes each
  return ``new_game(seed=CORRUPTION_RECOVERY_SEED)`` with a state_hash
  matching the frozen expected hash:
    (a) missing key in the dict (KeyError path)
    (b) unknown schema version (version != 1 path)
    (c) bad field types in the state sub-dict (TypeError path)
- ``CORRUPTION_RECOVERY_SEED`` is a module-level constant equal to ``0``.
  The recovery path MUST NOT derive a seed from ``time.time()`` (that would
  break the determinism invariant).

File I/O (``load()`` + backup fallback) lives in ``test_load.py``.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from htop_tycoon.domain.state import GameState, new_game, state_hash
from htop_tycoon.persistence.deserialize import (
    CORRUPTION_RECOVERY_SEED,
    deserialize,
)
from htop_tycoon.persistence.serialize import SCHEMA_VERSION, serialize

# Frozen expected state_hash for ``new_game(seed=CORRUPTION_RECOVERY_SEED)``.
# Computed empirically via ``state_hash(new_game(0))``; this is a SHA-256 hex
# digest and is fully deterministic for the locked v0.1.0 state schema.
RECOVERY_STATE_HASH: str = "0659738b9d8d2105f0b18dec093a4965a697db28a43aff9e36d124cb29b612c4"


# ---------------------------------------------------------------------------
# Helpers: build minimal valid envelopes for corruption tests
# ---------------------------------------------------------------------------


def _valid_company() -> dict[str, Any]:
    """Minimal valid Company sub-dict."""
    return {"id": "company-1", "name": "x", "cash": 0, "market_cap": 0}


def _valid_game_time() -> dict[str, Any]:
    """Minimal valid GameTime sub-dict."""
    return {"year": 1, "quarter": 1, "week": 1}


def _valid_state() -> dict[str, Any]:
    """Minimal valid state sub-dict with all required GameState fields.

    Each corruption test overrides one (or more) keys to exercise a specific
    failure mode without copying the entire skeleton.
    """
    return {
        "company": _valid_company(),
        "departments": {},
        "employees": {},
        "products": {},
        "competitors": {},
        "events_active": [],
        "ending_history": [],
        "secret_investor_cleared": False,
        "tick": 0,
        "rng_seed": 42,
        "game_time": _valid_game_time(),
        "version": 1,
    }


def _envelope(**overrides: Any) -> dict[str, Any]:
    """Build a valid v1 envelope with optional field overrides.

    Use this to express corruption as a *diff* from a valid envelope rather
    than restating the whole tree each test. Example::

        _envelope(version=999)        # corruption: bad version
        _envelope(state=_valid_state())  # top-level state is fully replaced
    """
    base: dict[str, Any] = {
        "version": SCHEMA_VERSION,
        "state": _valid_state(),
        "saved_at_iso": "x",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Module-level constant: CORRUPTION_RECOVERY_SEED
# ---------------------------------------------------------------------------


def test_corruption_recovery_seed_is_zero_constant() -> None:
    """The recovery seed MUST be the literal int 0 (NOT time.time()).

    This is the determinism invariant: every corruption path must yield the
    exact same state hash across runs. A time-derived seed would vary.
    """
    assert CORRUPTION_RECOVERY_SEED == 0
    assert isinstance(CORRUPTION_RECOVERY_SEED, int)


def test_corruption_recovery_seed_is_not_time_derived() -> None:
    """Sanity: the recovery seed is fixed; calling it twice yields the same hash.

    If the seed were derived from ``time.time()`` this property would still
    hold *within a single process* but the constant would be a function call
    rather than an int. Combined with the literal-0 check above, this locks
    the invariant.
    """
    s1 = new_game(CORRUPTION_RECOVERY_SEED)
    s2 = new_game(CORRUPTION_RECOVERY_SEED)
    assert state_hash(s1) == state_hash(s2) == RECOVERY_STATE_HASH


# ---------------------------------------------------------------------------
# deserialize() — happy path: round-trip
# ---------------------------------------------------------------------------


def test_deserialize_round_trip_preserves_state_hash() -> None:
    """serialize(new_game(42)) -> deserialize -> state_hash matches the original."""
    original = new_game(42)
    payload = serialize(original)
    reconstructed = deserialize(payload)
    assert state_hash(reconstructed) == state_hash(original)


def test_deserialize_round_trip_preserves_after_replace() -> None:
    """A modified state (tick advanced) must round-trip without hash drift."""
    original = new_game(42)
    advanced = dataclasses.replace(original, tick=7)
    payload = serialize(advanced)
    reconstructed = deserialize(payload)
    assert state_hash(reconstructed) == state_hash(advanced)
    assert reconstructed.tick == 7
    assert reconstructed.rng_seed == 42


def test_deserialize_round_trip_preserves_after_secret_flag_set() -> None:
    """A state with secret_investor_cleared=True must round-trip too."""
    original = new_game(42)
    flagged = dataclasses.replace(original, secret_investor_cleared=True)
    payload = serialize(flagged)
    reconstructed = deserialize(payload)
    assert state_hash(reconstructed) == state_hash(flagged)
    assert reconstructed.secret_investor_cleared is True


def test_deserialize_returns_game_state_instance() -> None:
    """deserialize must return a GameState (never None, never a raw dict)."""
    payload = serialize(new_game(42))
    reconstructed = deserialize(payload)
    assert isinstance(reconstructed, GameState)


# ---------------------------------------------------------------------------
# deserialize() — corruption mode (a): missing-key dict
# ---------------------------------------------------------------------------


def test_deserialize_missing_top_level_version_key_recovers() -> None:
    """A dict missing the 'version' key must return new_game(seed=0)."""
    bad = _envelope()
    del bad["version"]
    result = deserialize(bad)
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_deserialize_missing_top_level_state_key_recovers() -> None:
    """A dict missing the 'state' key must return new_game(seed=0)."""
    bad = _envelope()
    del bad["state"]
    result = deserialize(bad)
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_deserialize_missing_state_subkey_recovers() -> None:
    """A state sub-dict missing 'company' must recover (KeyError on construction)."""
    state = _valid_state()
    del state["company"]  # missing -> KeyError when GameState(company=...) runs
    result = deserialize(_envelope(state=state))
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_deserialize_missing_company_field_recovers() -> None:
    """A 'state.company' sub-dict missing a Company field must recover."""
    company = _valid_company()
    del company["market_cap"]  # missing -> KeyError on Company(...)
    state = _valid_state()
    state["company"] = company
    result = deserialize(_envelope(state=state))
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_deserialize_missing_game_time_field_recovers() -> None:
    """A 'state.game_time' sub-dict missing 'week' must recover."""
    state = _valid_state()
    state["game_time"] = {"year": 1, "quarter": 1}  # week missing
    result = deserialize(_envelope(state=state))
    assert state_hash(result) == RECOVERY_STATE_HASH


# ---------------------------------------------------------------------------
# deserialize() — corruption mode (b): bad version
# ---------------------------------------------------------------------------


def test_deserialize_version_zero_recovers() -> None:
    """version=0 (older than the locked v1) must recover."""
    result = deserialize(_envelope(version=0))
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_deserialize_version_999_recovers() -> None:
    """version=999 (future schema with no migration) must recover."""
    result = deserialize(_envelope(version=999))
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_deserialize_version_negative_recovers() -> None:
    """version=-1 (nonsense value) must recover."""
    result = deserialize(_envelope(version=-1))
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_deserialize_version_string_recovers() -> None:
    """version='1' (string, not int) must recover (bad field type path)."""
    result = deserialize(_envelope(version="1"))  # type: ignore[arg-type]
    assert state_hash(result) == RECOVERY_STATE_HASH


# ---------------------------------------------------------------------------
# deserialize() — corruption mode (c): bad field types
# ---------------------------------------------------------------------------


def test_deserialize_bad_company_type_recovers() -> None:
    """company as a string (not a dict) must recover (TypeError on Company(**s['company']))."""
    state = _valid_state()
    state["company"] = "not-a-dict"  # type: ignore[assignment]
    result = deserialize(_envelope(state=state))
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_deserialize_bad_quarter_value_recovers() -> None:
    """game_time.quarter out of [1,4] range must recover (ValueError)."""
    state = _valid_state()
    state["game_time"] = {"year": 1, "quarter": 99, "week": 1}
    result = deserialize(_envelope(state=state))
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_deserialize_state_not_a_dict_recovers() -> None:
    """state value is a string (not a dict) must recover."""
    result = deserialize(_envelope(state="not-a-dict"))  # type: ignore[arg-type]
    assert state_hash(result) == RECOVERY_STATE_HASH


# ---------------------------------------------------------------------------
# deserialize() — never raises (even on truly exotic inputs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "garbage",
    [
        None,
        "string",
        42,
        ["list", "of", "stuff"],
        True,
    ],
)
def test_deserialize_never_raises_on_garbage(garbage: object) -> None:
    """deserialize MUST NOT raise on any input; it always returns a GameState."""
    # The signature requires a dict; non-dict inputs must still not raise
    # because the corruption recovery swallows everything.
    result = deserialize(garbage)  # type: ignore[arg-type]
    assert state_hash(result) == RECOVERY_STATE_HASH


# ---------------------------------------------------------------------------
# Determinism invariant: corruption always yields the same state_hash
# ---------------------------------------------------------------------------


def test_recovery_state_hash_is_stable_across_corruption_paths() -> None:
    """All corruption paths must produce the EXACT same state_hash.

    This is the determinism invariant the spec calls out: the recovery seed
    is a constant, not time-derived.
    """
    no_version = _envelope()
    del no_version["version"]
    corruptions: list[object] = [
        no_version,  # missing 'version'
        {"version": SCHEMA_VERSION},  # missing 'state'
        {"version": 999, "state": {}, "saved_at_iso": "x"},  # bad version
        {"version": SCHEMA_VERSION, "state": "x", "saved_at_iso": "x"},  # bad state type
        {"version": SCHEMA_VERSION, "state": {"company": {}}},  # missing fields
    ]
    hashes = {state_hash(deserialize(c)) for c in corruptions}  # type: ignore[arg-type]
    assert hashes == {RECOVERY_STATE_HASH}, (
        f"All corruption paths must yield the same hash; got {hashes!r}"
    )
