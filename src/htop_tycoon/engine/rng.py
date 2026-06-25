"""Seeded ``GameRNG`` — single sanctioned adapter for ``random.Random``.

Per AGENTS.md "Determinism" invariant, every random flow in the codebase
must go through ``GameRNG(seed)``. The underlying ``random.Random`` instance
is intentionally kept private (name-mangled ``__impl``) so callers cannot
grab it and bypass the typed surface.

Methods:
    int(lo, hi)             -> int in [lo, hi] inclusive
    float()                 -> float in [0.0, 1.0)
    choice(seq)             -> one element drawn from ``seq``
    weighted_choice(seq, w) -> one element drawn with probability proportional to ``w``
    event(p)                -> True with probability ``p`` (per-tick event gate)

Determinism contract:
    GameRNG(seed) followed by any fixed sequence of calls yields a
    byte-identical sequence on every run, on every platform Python
    supports. This is locked by the SHA256 invariant test in
    ``tests/test_rng.py``.
"""

from __future__ import annotations

import builtins  # noqa: F401  # disambiguates class method `float` from builtin `float`
import random as _stdlib_random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class GameRNG:
    """Seedable RNG with a typed, lockable surface.

    The underlying ``random.Random`` instance is stored under a name-mangled
    attribute (``__impl``) so external callers cannot grab it directly. This
    enforces the project invariant that every random call funnels through
    this class.
    """

    __slots__ = ("__impl",)

    def __init__(self, seed: int) -> None:
        """Initialize the RNG with an integer seed.

        Given: an integer ``seed``
        When: ``GameRNG(seed)`` is constructed
        Then: a fresh ``random.Random(seed)`` instance is bound internally
        """
        # ``__impl`` is name-mangled to ``_GameRNG__impl``; combined with
        # ``__slots__`` there is no public attribute path to the underlying
        # random.Random.
        object.__setattr__(self, "_GameRNG__impl", _stdlib_random.Random(seed))

    # ------------------------------------------------------------------ helpers

    def _impl(self) -> _stdlib_random.Random:
        """Return the underlying random.Random. Private to the class."""
        # ``object.__getattribute__`` resolves the mangled name within the
        # class body, but the name is still inaccessible to outside code
        # because the leading underscore is mangled away by the compiler.
        impl: _stdlib_random.Random = object.__getattribute__(
            self, "_GameRNG__impl"
        )
        return impl

    # ------------------------------------------------------------------ surface

    def int(self, lo: int, hi: int) -> int:
        """Return a random integer in the inclusive range ``[lo, hi]``."""
        if hi < lo:
            raise ValueError(f"hi ({hi}) must be >= lo ({lo})")
        # ``randint`` is inclusive on both ends — matches the spec.
        return self._impl().randint(lo, hi)

    def float(self) -> builtins.float:
        """Return a random float in the half-open interval ``[0.0, 1.0)``."""
        return self._impl().random()

    def choice(self, seq: Sequence[T]) -> T:
        """Return one element drawn uniformly from ``seq``.

        Raises ``IndexError`` if ``seq`` is empty (delegated to stdlib).
        """
        if len(seq) == 0:
            raise IndexError("Cannot choose from an empty sequence")
        return self._impl().choice(seq)

    def weighted_choice(
        self,
        seq: Sequence[T],
        weights: Sequence[builtins.float],
    ) -> T:
        """Return one element drawn with probability proportional to ``weights``.

        ``weights`` must be non-negative and contain at least one positive
        entry; length must match ``seq``. Raises ``ValueError`` otherwise.
        """
        if len(seq) != len(weights):
            raise ValueError(
                f"seq and weights length mismatch: {len(seq)} vs {len(weights)}"
            )
        if len(seq) == 0:
            raise IndexError("Cannot choose from an empty sequence")
        # Defensive: every weight must be >= 0 and the total must be > 0.
        if any(w < 0 for w in weights):
            raise ValueError("weights must be non-negative")
        if sum(weights) <= 0:
            raise ValueError("sum of weights must be > 0")
        return self._impl().choices(seq, weights=weights, k=1)[0]

    def event(self, per_tick_probability: builtins.float) -> bool:
        """Return True with probability ``per_tick_probability``.

        ``per_tick_probability`` is clamped to ``[0.0, 1.0]``. A probability
        of ``0.0`` always returns False; ``1.0`` always returns True.
        """
        if per_tick_probability <= 0.0:
            return False
        if per_tick_probability >= 1.0:
            return True
        return self._impl().random() < per_tick_probability
