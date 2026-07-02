"""T1.5 RED: GameRng determinism + boundary checks."""

from __future__ import annotations

import pytest

from htop_tycoon.domain.rng import GameRng


def test_same_seed_same_int_range_sequence() -> None:
    a = GameRng(42)
    b = GameRng(42)
    seq_a = [a.int_range(1, 100) for _ in range(100)]
    seq_b = [b.int_range(1, 100) for _ in range(100)]
    assert seq_a == seq_b


def test_int_range_within_bounds() -> None:
    rng = GameRng(0)
    for _ in range(1000):
        v = rng.int_range(5, 10)
        assert 5 <= v <= 10


def test_int_range_rejects_inverted() -> None:
    rng = GameRng(0)
    with pytest.raises(ValueError):
        rng.int_range(10, 5)


def test_choice_picks_from_seq() -> None:
    rng = GameRng(0)
    seq = ["a", "b", "c"]
    for _ in range(50):
        assert rng.choice(seq) in seq


def test_choice_rejects_empty() -> None:
    rng = GameRng(0)
    with pytest.raises(ValueError):
        rng.choice([])


def test_weighted_choice_respects_distribution() -> None:
    rng = GameRng(0)
    items = ["rare", "common"]
    weights = [1.0, 9.0]
    counts = {"rare": 0, "common": 0}
    for _ in range(10_000):
        counts[rng.weighted_choice(items, weights)] += 1
    common_ratio = counts["common"] / 10_000
    assert 0.88 < common_ratio < 0.92, f"Expected ~0.90, got {common_ratio}"


def test_weighted_choice_deterministic_with_seed() -> None:
    a = GameRng(7)
    b = GameRng(7)
    seq_a = [a.weighted_choice(["a", "b"], [1.0, 1.0]) for _ in range(50)]
    seq_b = [b.weighted_choice(["a", "b"], [1.0, 1.0]) for _ in range(50)]
    assert seq_a == seq_b


def test_shuffle_does_not_mutate_input() -> None:
    rng = GameRng(0)
    original = [1, 2, 3, 4, 5]
    snapshot = original.copy()
    rng.shuffle(original)
    assert original == snapshot


def test_shuffle_returns_new_list() -> None:
    rng = GameRng(0)
    result = rng.shuffle([1, 2, 3])
    assert isinstance(result, list)
    assert sorted(result) == [1, 2, 3]


def test_shuffle_deterministic_with_seed() -> None:
    a = GameRng(11)
    b = GameRng(11)
    out_a = a.shuffle(list(range(20)))
    out_b = b.shuffle(list(range(20)))
    assert out_a == out_b


def test_pinned_seed_pinned_sequence() -> None:
    """Regression anchor for engine determinism.

    Locked on Python 3.12.10 (macOS aarch64). If this changes across
    Python versions, every downstream snapshot test breaks.
    """
    rng = GameRng(42)
    seq = [rng.int_range(0, 10_000) for _ in range(10)]
    assert seq == [
        1824,
        409,
        4506,
        4012,
        3657,
        2286,
        1679,
        8935,
        1424,
        9674,
    ]


def test_rejects_non_int_seed() -> None:
    with pytest.raises(TypeError):
        GameRng("seed")  # type: ignore[arg-type]
