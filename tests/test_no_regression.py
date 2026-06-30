"""Regression guard for v0.2.0 default GameState hash (T46).

Wave 9 (T46) — every time ``GameState`` gains a new field or the
``domain.regimes`` / ``domain.focus`` defaults change, the canonical
``state_hash(new_game(seed=42))`` value changes too. This file pins
that hash as a single source of truth so any future drift is caught
in one place.

Lock-in protocol:
  1. ``new_game(seed=42)`` is the canonical empty starting state.
  2. After W7-W9 (regime, dept_focus defaults) it includes:
     - company.cash=50000, market_cap=50000
     - regime=RegimeState(NORMAL, 0, 0)
     - dept_focus={}  (empty: no depts in fresh state)
     - version=1 (GameState's own version literal)
  3. The hash below must match. Drift -> tests fail.

The hash was captured with the v0.2.0 plan fully merged, after T45.
If you change a default in ``new_game`` or in ``RegimeState`` /
``default_dept_focus``, you MUST update the literal below AND add a
note in CHANGELOG.md (T47).
"""

from __future__ import annotations

from htop_tycoon.domain.state import new_game, state_hash

# Frozen literal — change with care. See protocol above.
V2_DEFAULT_STATE_HASH: str = "775a57d7014ea7c7798b95715c355630a8bd868939f052c1b855fd380fac88c5"


class TestV2DefaultStateHashRegression:
    def test_new_game_default_state_hash_is_frozen_v2(self) -> None:
        """The hash of ``new_game(seed=42)`` is the canonical v2 default.
        Drift here signals an unintended change to GameState defaults
        or to RegimeState/RegimeType values.
        """
        state = new_game(rng_seed=42)
        actual = state_hash(state)
        assert actual == V2_DEFAULT_STATE_HASH, (
            f"v2 default state_hash drift: actual={actual!r}, "
            f"expected={V2_DEFAULT_STATE_HASH!r}. If you intentionally "
            f"changed a default, update this literal AND CHANGELOG.md "
            f"per T46 + T47."
        )

    def test_hash_is_byte_deterministic_across_two_runs(self) -> None:
        """Two fresh constructions produce identical hashes
        (defends against accidental seeding of RNG/object identity).
        """
        h1 = state_hash(new_game(rng_seed=42))
        h2 = state_hash(new_game(rng_seed=42))
        assert h1 == h2

    def test_different_seed_produces_different_hash(self) -> None:
        """Different seeds → different hashes (rng_seed field changes)."""
        h42 = state_hash(new_game(rng_seed=42))
        h99 = state_hash(new_game(rng_seed=99))
        assert h42 != h99, "different seeds must produce different hashes"
