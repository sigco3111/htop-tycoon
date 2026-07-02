"""Market state — popularity and trend for a given platform/console.

Frozen dataclass so callers never accidentally mutate shared market data.
`default_for_platform` is the only factory; tests cover all 4 platforms
and the CONSOLE→NOVA default mapping.
"""

from __future__ import annotations

from dataclasses import dataclass

from htop_tycoon.domain.enums import Console, Platform

PLATFORM_POPULARITY: dict[Platform, float] = {
    Platform.PC: 1.0,
    Platform.MOBILE: 1.3,
    Platform.CONSOLE: 0.8,
    Platform.HANDHELD: 0.6,
}

CONSOLE_POPULARITY: dict[Console, float] = {
    Console.PC: 1.0,
    Console.GENESIS_X: 1.1,
    Console.NOVA: 0.9,
    Console.PIXEL_2: 1.2,
    Console.ARCADE: 0.7,
    Console.ATARI_Q: 0.6,
}

DEFAULT_TREND: float = 1.0

# When a project's platform is CONSOLE, default to NOVA if no console set.
_DEFAULT_CONSOLE_FOR_PLATFORM: Platform = Platform.CONSOLE
_DEFAULT_CONSOLE_VALUE: Console = Console.NOVA


@dataclass(frozen=True, slots=True)
class MarketState:
    """Popularity and trend for a specific platform (+ optional console)."""

    console: Console | None
    platform: Platform
    popularity: float
    trend: float

    def __post_init__(self) -> None:
        if not isinstance(self.platform, Platform):
            raise TypeError(
                f"platform must be Platform, got {type(self.platform).__name__}"
            )
        if not isinstance(self.popularity, (int, float)):
            raise TypeError(
                f"popularity must be numeric, got {type(self.popularity).__name__}"
            )
        if not isinstance(self.trend, (int, float)):
            raise TypeError(
                f"trend must be numeric, got {type(self.trend).__name__}"
            )
        if self.popularity <= 0:
            raise ValueError(f"popularity must be > 0, got {self.popularity}")
        if self.trend <= 0:
            raise ValueError(f"trend must be > 0, got {self.trend}")

    @classmethod
    def default_for_platform(cls, platform: Platform) -> MarketState:
        """Return a MarketState seeded with default popularity + trend."""
        if platform == _DEFAULT_CONSOLE_FOR_PLATFORM:
            return cls(
                console=_DEFAULT_CONSOLE_VALUE,
                platform=platform,
                popularity=CONSOLE_POPULARITY[_DEFAULT_CONSOLE_VALUE],
                trend=DEFAULT_TREND,
            )
        return cls(
            console=None,
            platform=platform,
            popularity=PLATFORM_POPULARITY[platform],
            trend=DEFAULT_TREND,
        )
