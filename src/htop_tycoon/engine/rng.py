"""Deterministic RNG wrapper for htop-tycoon v3.0.

Spec §5.3 + AGENTS.md invariants:
- All randomness in the engine MUST flow through `GameRNG(seed)`.
- No bare `import random` / `from random` exists anywhere outside this module;
  this is enforced by `tests/test_rng.py::test_no_bare_random_import_outside_rng`.
- `CORRUPTION_RECOVERY_SEED = 0` is a constant sentinel used when persisted seeds
  fail to parse. NEVER derive it from `time.time()`.

This module is allowed to import the stdlib `random` package: it is the sole
gateway that keeps the rest of the engine deterministic.
"""
from __future__ import annotations

import random as _stdlib_random
from collections.abc import Sequence
from typing import TypeVar

__all__ = ["CORRUPTION_RECOVERY_SEED", "GameRNG"]

T = TypeVar("T")

# Spec §5.3: never derive recovery seed from time.time(). Sentinel value used by
# the persistence layer when a save file's RNG seed is unreadable.
CORRUPTION_RECOVERY_SEED: int = 0


class GameRNG:
    """Deterministic RNG seeded once at construction time.

    Wraps `random.Random(seed)` to expose a narrow, project-friendly API.
    Every method is a thin pass-through to `random.Random`, so seed-to-output
    reproducibility is inherited from the stdlib.

    Args:
        seed: Non-negative integer seed. Negative values are accepted by the
            stdlib but discouraged here; we normalise via the underlying
            `random.Random` constructor.

    Example:
        >>> a = GameRNG(42)
        >>> b = GameRNG(42)
        >>> a.random() == b.random()
        True
    """

    __slots__ = ("_rng",)

    def __init__(self, seed: int) -> None:
        # Construct a fresh stdlib RNG so two GameRNG instances with the same
        # seed produce identical streams (the stdlib Random class uses the
        # Mersenne Twister and is fully deterministic given a seed).
        self._rng = _stdlib_random.Random(seed)

    # --- core API ---------------------------------------------------------

    def random(self) -> float:
        """Return the next random float in ``[0.0, 1.0)``."""
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        """Return a random integer ``N`` such that ``a <= N <= b``."""
        return self._rng.randint(a, b)

    def uniform(self, a: float, b: float) -> float:
        """Return a random float ``N`` such that ``a <= N < b``."""
        return self._rng.uniform(a, b)

    def choice(self, seq: Sequence[T]) -> T:
        """Return a random element from a non-empty sequence.

        Raises:
            ValueError: If ``seq`` is empty.
        """
        if not seq:
            raise ValueError("Cannot choose from an empty sequence")
        return self._rng.choice(seq)

    def sample(self, population: Sequence[T], k: int) -> list[T]:
        """Return a ``k``-length list of unique elements chosen from ``population``.

        Raises:
            ValueError: If ``k`` is larger than ``len(population)``.
        """
        if k > len(population):
            raise ValueError("Sample larger than population")
        return self._rng.sample(population, k)

    def gauss(self, mu: float, sigma: float) -> float:
        """Gaussian distribution with mean ``mu`` and standard deviation ``sigma``."""
        return self._rng.gauss(mu, sigma)
