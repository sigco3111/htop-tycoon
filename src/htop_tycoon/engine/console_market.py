"""Console market — pricing + purchase logic.

Phase 2J. Console hardware the studio can purchase to launch titles on.
Owning a console unlocks SECRET ending (own_console + 1M units on it).
"""

from __future__ import annotations

from htop_tycoon.domain import CompanyState, Console, Money

CONSOLE_PRICES: dict[Console, int] = {
    Console.PC: 0,                # PC is free — assumed available without purchase
    Console.GENESIS_X: 80_000_00,
    Console.NOVA: 120_000_00,
    Console.PIXEL_2: 150_000_00,
    Console.ARCADE: 60_000_00,
    Console.ATARI_Q: 40_000_00,
}


def console_price(console: Console) -> Money:
    return Money(CONSOLE_PRICES[console])


def purchase_console(state: CompanyState, console: Console) -> CompanyState:
    """Buy a console and own it. Deducts cash. Raises if already owned or short."""
    if state.own_console == console:
        raise ValueError(f"already own console {console.value}")
    price = console_price(console).cents
    if price > 0 and state.cash.cents < price:
        raise ValueError(
            f"insufficient cash: need {Money(price)}, have {state.cash}"
        )
    return state.mark_own_console(console).adjust_cash(Money(-price))


def available_consoles() -> tuple[Console, ...]:
    """Consoles the studio can buy (excludes free PC)."""
    return tuple(c for c, price in CONSOLE_PRICES.items() if price > 0)
