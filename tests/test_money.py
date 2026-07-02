"""T1.3 RED: Money value object — arithmetic, ordering, display, frozen."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.domain.money import ZERO, Money


def test_money_stores_cents_as_int() -> None:
    assert Money(12345).cents == 12345


def test_money_display_whole_dollars() -> None:
    assert str(Money(100 * 100)) == "$100"


def test_money_display_with_change() -> None:
    assert str(Money(123 * 100 + 45)) == "$123.45"


def test_money_display_thousands_separator() -> None:
    assert str(Money(1_234_567_89)) == "$1,234,567.89"


def test_money_negative_display() -> None:
    assert str(Money(-100 * 100)) == "-$100"


def test_money_negative_cents_stored_as_negative() -> None:
    assert Money(-100).cents == -100


def test_money_addition() -> None:
    assert Money(100) + Money(50) == Money(150)


def test_money_subtraction() -> None:
    assert Money(100) - Money(30) == Money(70)


def test_money_subtraction_can_go_negative() -> None:
    """Negative cash is allowed (debt state)."""
    assert Money(30) - Money(100) == Money(-70)


def test_money_multiplication_by_int() -> None:
    assert Money(100) * 3 == Money(300)


def test_money_multiplication_by_negative_int() -> None:
    assert Money(100) * -2 == Money(-200)


def test_money_rmul() -> None:
    assert 3 * Money(100) == Money(300)


def test_money_negation() -> None:
    assert -Money(50) == Money(-50)


def test_money_ordering() -> None:
    assert Money(50) < Money(100)
    assert Money(100) > Money(50)
    assert Money(50) <= Money(50)
    assert Money(50) >= Money(50)


def test_money_equality() -> None:
    assert Money(100) == Money(100)
    assert Money(100) != Money(200)


def test_money_hashable() -> None:
    """Money must be hashable for use in sets/dict keys."""
    assert len({Money(100), Money(100), Money(200)}) == 2


def test_money_frozen() -> None:
    m = Money(1)
    with pytest.raises(FrozenInstanceError):
        m.cents = 2  # type: ignore[misc]


def test_money_zero_constant() -> None:
    assert ZERO.cents == 0


def test_money_rejects_non_int_cents() -> None:
    with pytest.raises(TypeError):
        Money(1.5)  # type: ignore[arg-type]
