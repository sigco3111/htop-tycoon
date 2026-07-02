"""Deterministic RNG wrapper — stdlib random.Random seeded for reproducibility."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from random import Random
from typing import TypeVar

T = TypeVar("T")


class GameRng:
    """Seeded RNG. Same seed + same calls = same sequence (deterministic).

    Public API intentionally narrow — callers cannot reach the underlying
    Random instance, so determinism is enforced by construction.
    """

    __slots__ = ("_rng",)

    def __init__(self, seed: int | None = None) -> None:
        if not isinstance(seed, (int, type(None))):
            raise TypeError(f"GameRng.seed must be int or None, got {type(seed).__name__}")
        self._rng = Random(seed)

    def int_range(self, lo: int, hi: int) -> int:
        """Return random int in [lo, hi] inclusive."""
        if lo > hi:
            raise ValueError(f"int_range: lo ({lo}) > hi ({hi})")
        return self._rng.randint(lo, hi)

    def choice(self, seq: Sequence[T]) -> T:
        if not seq:
            raise ValueError("choice: empty sequence")
        return self._rng.choice(seq)

    def weighted_choice(self, items: Sequence[T], weights: Sequence[float]) -> T:
        if not items:
            raise ValueError("weighted_choice: empty items")
        if len(items) != len(weights):
            raise ValueError(
                f"weighted_choice: items ({len(items)}) != weights ({len(weights)})"
            )
        if any(w < 0 for w in weights):
            raise ValueError("weighted_choice: weights must be non-negative")
        return self._rng.choices(items, weights=weights, k=1)[0]

    def shuffle(self, items: Iterable[T]) -> list[T]:
        """Return a new shuffled list; input is not mutated."""
        original = list(items)
        result = original.copy()
        self._rng.shuffle(result)
        return result

    def sample(self, items: Sequence[T], k: int) -> list[T]:
        if k < 0:
            raise ValueError(f"sample: k ({k}) < 0")
        if k > len(items):
            raise ValueError(f"sample: k ({k}) > len(items) ({len(items)})")
        return self._rng.sample(list(items), k)
