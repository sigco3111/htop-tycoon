"""Wave 3 partial-lock frozen-hash regression. Spec §7.3.

Verifies that ``GameState.compute_hash()`` at the three pinned day counts
(seed=42 → 100 / 1000 / 3650) matches the values captured in
``tests/fixtures/frozen_hashes.yaml`` after Wave 3.

Three consecutive CI runs must all pass (spec §7.3 step 5). If any hash
drifts, treat as a determinism regression: investigate engine / state /
serialization changes since the last capture before touching this fixture.

Per the Wave-3-partial-lock decision, Wave 5 (persistence) will
re-capture the actual literals; hash comparison here is the wave-3
invariant only. See ``tests/fixtures/frozen_hashes.yaml`` for the
capture procedure context.
"""
from __future__ import annotations

import os

import pytest
import yaml

from htop_tycoon.domain import GameState
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.tick import run_day

# Wave-3 partial-lock values; typed for IDE / mypy.
EXPECTED_HASHES: dict[int, str] = {
    100: "0792c34bbacfe4ae42e591f85a89264fa064403634d419cd2eeffa1e0662a913",
    1000: "c1050d96718e2021e01242cb3d2a43624098c113b1dc138a2f84bea1efcab3c8",
    3650: "fabf2a4ba9d7af30e7e995f8a5a0eaa177b4879af65f247a7d49c12d62ff4903",
}

# Faster smoke version for local dev — set HTOPTYCOON_FROZEN_HASH_FAST=1 to skip 3650.
_QUICK_TARGETS = (100, 1000)
_FULL_TARGETS = (100, 1000, 3650)


def _target_days() -> tuple[int, ...]:
    if os.environ.get("HTOPTYCOON_FROZEN_HASH_FAST") == "1":
        return _QUICK_TARGETS
    return _FULL_TARGETS


def _state_at(seed: int, day_target: int) -> GameState:
    """Run ``tick.run_day`` for ``day_target`` ticks, starting from a fresh state."""
    rng = GameRNG(seed)
    state = GameState(rng_seed=seed)
    for _ in range(day_target):
        state, _events = run_day(state, rng)
    return state


@pytest.mark.parametrize("day_target", _target_days())
def test_frozen_hash_matches_spec_lock_at_seed42(day_target: int) -> None:
    expected = EXPECTED_HASHES[day_target]
    state = _state_at(42, day_target)
    assert state.compute_hash() == expected, (
        f"determinism regression at seed=42, day={day_target}: "
        f"expected {expected}, got {state.compute_hash()}"
    )


def test_frozen_hash_yaml_fixture_is_consistent() -> None:
    """Sanity check: the YAML fixture must equal the hard-coded EXPECTED_HASHES dict.

    Catches drift between the fixture file (which is the canonical source
    per spec §7.3) and the dictionary baked into the test module.
    """
    fixture_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "fixtures", "frozen_hashes.yaml"
    )
    with open(fixture_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data["seed"] == 42
    assert data["state_hash_at_day"] == {
        int(k): v for k, v in EXPECTED_HASHES.items()
    }, "tests/fixtures/frozen_hashes.yaml drifted from EXPECTED_HASHES; "
    "update both or investigate why."
