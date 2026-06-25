"""Auxiliary tests for T33: lock-in determinism + seeds.yaml shape.

These tests back the main reachability tests in ``test_endings_reachable.py``:

- ``TestEndingsReachableDeterminism`` proves that the crafted-state
  pipeline is fully deterministic: same (seed, expected_tick, state
  builder) yields the same (hash, ending) on every run. This is the
  second half of the lock-in protocol (per plan line 689 / T32).
- ``TestSeedsYamlShape`` guards the ``src/htop_tycoon/data/seeds.yaml``
  contract: 5 ending keys, each with ``seed``, ``expected_tick``,
  ``command_line``; no emoji codepoints (project-wide rule per AGENTS.md).

The frozen literal placeholders (``EXPECTED_*_HASH``, ``EXPECTED_*_TICK``)
are imported from the main test file so the literals live in one place.
"""

from __future__ import annotations

import pytest

from htop_tycoon.data import load_seeds
from tests.test_endings_reachable import (
    _SEEDS_PATH,
    EXPECTED_HOSTILE_MA_TICK,
    EXPECTED_IPO_TICK,
    EXPECTED_SECRET_TICK,
    EXPECTED_VOLUNTARY_SALE_TICK,
    SEED_HOSTILE_MA,
    SEED_IPO,
    SEED_SECRET,
    SEED_VOLUNTARY_SALE,
    _build_hostile_ma_state,
    _build_ipo_state,
    _build_secret_state,
    _build_voluntary_sale_state,
    _drive_crafted_state,
    _load_seeds_fixture,
)

# ===========================================================================
# Lock-in protocol: same inputs yield same outputs across runs.
# ===========================================================================


class TestEndingsReachableDeterminism:
    """The T33 lock-in protocol: each crafted-state test is fully deterministic."""

    @staticmethod
    def _tick_default(expected: int | None) -> int:
        return expected if expected is not None else 1

    def test_ipo_deterministic_across_runs(self) -> None:
        """Run IPO crafted-state test twice; assert identical hash."""
        state = _build_ipo_state()
        n = self._tick_default(EXPECTED_IPO_TICK)
        diag_a = _drive_crafted_state(state, seed=SEED_IPO, n_ticks=n)
        diag_b = _drive_crafted_state(state, seed=SEED_IPO, n_ticks=n)
        assert diag_a["hash"] == diag_b["hash"]
        assert diag_a["ending_pre_apply"] == diag_b["ending_pre_apply"]

    def test_hostile_ma_deterministic_across_runs(self) -> None:
        state = _build_hostile_ma_state()
        n = self._tick_default(EXPECTED_HOSTILE_MA_TICK)
        diag_a = _drive_crafted_state(state, seed=SEED_HOSTILE_MA, n_ticks=n)
        diag_b = _drive_crafted_state(state, seed=SEED_HOSTILE_MA, n_ticks=n)
        assert diag_a["hash"] == diag_b["hash"]
        assert diag_a["ending_pre_apply"] == diag_b["ending_pre_apply"]

    def test_voluntary_sale_deterministic_across_runs(self) -> None:
        state = _build_voluntary_sale_state()
        n = self._tick_default(EXPECTED_VOLUNTARY_SALE_TICK)
        diag_a = _drive_crafted_state(state, seed=SEED_VOLUNTARY_SALE, n_ticks=n)
        diag_b = _drive_crafted_state(state, seed=SEED_VOLUNTARY_SALE, n_ticks=n)
        assert diag_a["hash"] == diag_b["hash"]
        assert diag_a["ending_pre_apply"] == diag_b["ending_pre_apply"]

    def test_secret_deterministic_across_runs(self) -> None:
        state = _build_secret_state()
        n = self._tick_default(EXPECTED_SECRET_TICK)
        diag_a = _drive_crafted_state(state, seed=SEED_SECRET, n_ticks=n)
        diag_b = _drive_crafted_state(state, seed=SEED_SECRET, n_ticks=n)
        assert diag_a["hash"] == diag_b["hash"]
        assert diag_a["ending_pre_apply"] == diag_b["ending_pre_apply"]


# ===========================================================================
# Anti-pattern guards + seeds.yaml shape.
# ===========================================================================


class TestSeedsYamlShape:
    """seeds.yaml must contain a top-level ``endings`` mapping with all 5 keys."""

    def test_seeds_yaml_has_all_five_endings(self) -> None:
        seeds = _load_seeds_fixture()
        expected = {"BANKRUPTCY", "IPO", "HOSTILE_MA", "VOLUNTARY_SALE", "SECRET"}
        assert set(seeds.keys()) == expected, (
            f"seeds.yaml endings keys mismatch. "
            f"actual={sorted(seeds.keys())} expected={sorted(expected)}"
        )

    def test_each_fixture_has_required_fields(self) -> None:
        """Each ending fixture has ``seed``, ``expected_tick``, ``command_line``."""
        seeds = _load_seeds_fixture()
        for ending_key, fixture in seeds.items():
            assert "seed" in fixture, f"{ending_key} missing 'seed'"
            assert "expected_tick" in fixture, f"{ending_key} missing 'expected_tick'"
            assert "command_line" in fixture, f"{ending_key} missing 'command_line'"
            assert isinstance(fixture["seed"], int)
            assert isinstance(fixture["expected_tick"], int)
            assert isinstance(fixture["command_line"], str)

    def test_no_emoji_in_seeds_yaml(self) -> None:
        """Project rule: no emoji in source/docs."""
        content = _SEEDS_PATH.read_text(encoding="utf-8")
        for ch in content:
            cp = ord(ch)
            if cp >= 0x1F000:
                pytest.fail(f"emoji codepoint U+{cp:04X} found in seeds.yaml")

    def test_load_seeds_caches(self) -> None:
        """load_seeds() is lru_cached; same call returns the same dict object."""
        a = load_seeds()
        b = load_seeds()
        assert a is b
