"""ConsoleMarketScreen modal — show purchasable consoles."""

from __future__ import annotations

from htop_tycoon.domain import CompanyState, Console
from htop_tycoon.engine.console_market import (
    available_consoles,
    console_price,
)


class ConsoleMarketScreen:
    """Modal data holder for console purchases.

    Lists consoles the studio can buy (excluding owned + free PC).
    select(idx) returns Console or None.
    """

    __slots__ = ("_state", "_listings")

    def __init__(self, state: CompanyState) -> None:
        self._state = state
        owned = state.own_console
        self._listings: list[Console] = [
            c for c in available_consoles() if c != owned
        ]

    @property
    def listings(self) -> tuple[Console, ...]:
        return tuple(self._listings)

    def render(self) -> str:
        lines = ["Console Market", ""]
        if self._state.own_console is not None:
            lines.append(f"You own: {self._state.own_console.value}")
        else:
            lines.append("You own: (none)")
        lines.append(f"Cash: {self._state.cash}")
        lines.append("")
        if not self._listings:
            lines.append("No consoles available for purchase.")
        else:
            lines.append("Available:")
            for idx, console in enumerate(self._listings, start=1):
                price = console_price(console)
                lines.append(f"  {idx}. {console.value:<12} {price}")
        lines.append("")
        lines.append(f"Press 1-{len(self._listings)} to buy, 'c' to close.")
        return "\n".join(lines)

    def select(self, idx: int) -> Console | None:
        if 1 <= idx <= len(self._listings):
            return self._listings[idx - 1]
        return None
