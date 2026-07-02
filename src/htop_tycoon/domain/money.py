"""Money value object — cents as int, dollar display, arithmetic, ordering.

Money is frozen and hashable so it can live in sets and as dict keys. Negative
balances are allowed (debt is a real state). Display uses thousands separators
and 2-decimal cents.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Money:
    cents: int

    def __post_init__(self) -> None:
        if not isinstance(self.cents, int):
            raise TypeError(f"Money.cents must be int, got {type(self.cents).__name__}")

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.cents + other.cents)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.cents - other.cents)

    def __mul__(self, factor: object) -> Money:
        if not isinstance(factor, int):
            return NotImplemented
        return Money(self.cents * factor)

    def __rmul__(self, factor: object) -> Money:
        return self.__mul__(factor)

    def __neg__(self) -> Money:
        return Money(-self.cents)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents < other.cents

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents <= other.cents

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents > other.cents

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents >= other.cents

    def __str__(self) -> str:
        sign = "-" if self.cents < 0 else ""
        abs_cents = abs(self.cents)
        dollars, remainder = divmod(abs_cents, 100)
        if remainder == 0:
            return f"{sign}${dollars:,}"
        return f"{sign}${dollars:,}.{remainder:02d}"

    def __repr__(self) -> str:
        return f"Money({self.cents})"


ZERO: Money = Money(0)
