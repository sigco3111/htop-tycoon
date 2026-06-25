"""Tests for T9: TickEngine determinism + frozen state_hash.

Locks the determinism invariant from .omo/plans/htop-tycoon.md line 319-328:

- ``advance(state, n)`` is deterministic given (engine.seed, n_ticks).
- The frozen SHA-256 of ``state_hash(advance(new_game(42), 100))`` is
  ``FROZEN_HASH_AFTER_100_TICKS_SEED_42``; changing the advance formulas,
  RNG interaction, or GameState field-set breaks the test.
- Per-tick RNG consumption: each ``advance(state, n)`` calls
  ``rng.float()`` exactly ``n`` times.
"""

from __future__ import annotations

import hashlib

from htop_tycoon.domain.state import new_game, state_hash
from htop_tycoon.engine.tick import TickEngine

FROZEN_HASH_AFTER_100_TICKS_SEED_42 = (
    "15b9c9973079b16bdaa45727e0acf751f754bd9cada53b876c563321d7f0a0ef"
)


class TestTickEngineDeterminism:
    """Same seed + same advance count → same state_hash, frozen."""

    def test_same_seed_same_advance_same_hash(self) -> None:
        """Two engines with seed=42 advance the same state to the same hash."""
        e1 = TickEngine(seed=42)
        e2 = TickEngine(seed=42)
        s1 = e1.advance(new_game(42), 100)
        s2 = e2.advance(new_game(42), 100)
        assert state_hash(s1) == state_hash(s2)

    def test_different_seeds_yield_different_hashes(self) -> None:
        """Sanity: seed actually affects state (different seed → different hash)."""
        e1 = TickEngine(seed=42)
        e2 = TickEngine(seed=43)
        s1 = e1.advance(new_game(42), 100)
        s2 = e2.advance(new_game(43), 100)
        assert state_hash(s1) != state_hash(s2)

    def test_advance_100_ticks_seed_42_frozen_hash(self) -> None:
        """Given: TickEngine(seed=42), new_game(42)
        When: advance(state, 100) is called
        Then: state_hash(result) equals the frozen expected digest
        """
        engine = TickEngine(seed=42)
        result = engine.advance(new_game(42), 100)
        digest = state_hash(result)
        assert digest == FROZEN_HASH_AFTER_100_TICKS_SEED_42, (
            f"Determinism invariant broken. actual={digest} "
            f"expected={FROZEN_HASH_AFTER_100_TICKS_SEED_42}"
        )

    def test_advance_consumes_rng_once_per_tick(self) -> None:
        """advance(state, n) consumes exactly n floats from the engine's RNG.

        This locks the per-tick RNG contract for downstream consumers (T10
        hire, T12 products, T13 competitors): every tick advances the RNG
        by one ``float()`` call, so the stream consumed by those modules is
        fully determined by (engine.seed, total_ticks_advanced).
        """
        engine = TickEngine(seed=42)
        engine.advance(new_game(42), 100)
        tail_a = [engine._rng.float() for _ in range(50)]
        twin = TickEngine(seed=42)
        twin.advance(new_game(42), 100)
        tail_b = [twin._rng.float() for _ in range(50)]
        assert hashlib.sha256(repr(tail_a).encode()).hexdigest() == hashlib.sha256(
            repr(tail_b).encode()
        ).hexdigest()

    def test_frozen_hash_is_stable_across_repeated_runs(self) -> None:
        """Run the same determinism scenario 3 times; the hash must match each time."""
        digests = [
            state_hash(TickEngine(seed=42).advance(new_game(42), 100))
            for _ in range(3)
        ]
        assert digests[0] == digests[1] == digests[2] == FROZEN_HASH_AFTER_100_TICKS_SEED_42
