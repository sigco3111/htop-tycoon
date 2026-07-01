"""Tests for the deterministic GameRNG wrapper.

Enforces two invariants:
  1. GameRNG(seed) is reproducible and exposes a stable interface.
  2. No bare `import random` / `from random` exists outside engine/rng.py.
"""
import os
import subprocess

import pytest

from htop_tycoon.engine.rng import CORRUPTION_RECOVERY_SEED, GameRNG


def test_gamerng_seed_reproducibility() -> None:
    a = GameRNG(42)
    b = GameRNG(42)
    assert [a.random() for _ in range(10)] == [b.random() for _ in range(10)]


def test_gamerng_different_seeds_differ() -> None:
    a = GameRNG(42)
    b = GameRNG(43)
    assert a.random() != b.random()


def test_gamerng_randint_in_range() -> None:
    rng = GameRNG(42)
    for _ in range(100):
        v = rng.randint(0, 10)
        assert 0 <= v <= 10


def test_gamerng_uniform_in_range() -> None:
    rng = GameRNG(42)
    for _ in range(100):
        v = rng.uniform(0.0, 1.0)
        assert 0.0 <= v <= 1.0


def test_gamerng_choice_from_list() -> None:
    rng = GameRNG(42)
    items = [1, 2, 3]
    for _ in range(100):
        assert rng.choice(items) in items


def test_gamerng_choice_empty_raises() -> None:
    rng = GameRNG(42)
    with pytest.raises(ValueError):
        rng.choice([])


def test_gamerng_sample_respects_k() -> None:
    rng = GameRNG(42)
    items = [1, 2, 3, 4, 5]
    for _ in range(50):
        result = rng.sample(items, 3)
        assert len(result) == 3
        assert all(x in items for x in result)


def test_gamerng_sample_k_too_large_raises() -> None:
    rng = GameRNG(42)
    with pytest.raises(ValueError):
        rng.sample([1, 2], 3)


def test_gamerng_gauss_distribution() -> None:
    rng = GameRNG(42)
    samples = [rng.gauss(0, 1) for _ in range(1000)]
    mean = sum(samples) / len(samples)
    assert abs(mean) < 0.3  # should be near 0 with high probability


def test_corruption_recovery_seed_is_zero() -> None:
    """Spec §5.3 + AGENTS.md: NEVER derive from time.time()."""
    assert CORRUPTION_RECOVERY_SEED == 0


def test_no_bare_random_import_outside_rng() -> None:
    """Enforce anti-pattern: no `import random` / `from random` outside engine/rng.py.

    Uses ``grep -E`` (extended regex) so ``|`` is treated as alternation;
    without ``-E``, BRE treats ``|`` as a literal character and the test
    vacuously passes (regressions slip through silently). Also CWD-independent
    via absolute path so IDE test runners behave correctly.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(repo_root, "src", "htop_tycoon")
    allowed_abs = os.path.join(src_path, "engine", "rng.py")
    result = subprocess.run(
        ["grep", "-rnE", "--include=*.py", r"^(import|from)\s+random\b", src_path],
        capture_output=True,
        text=True,
        check=False,
    )
    violations = [
        line for line in result.stdout.strip().splitlines()
        if allowed_abs not in line
    ]
    assert violations == [], f"Bare random import found: {violations}"
