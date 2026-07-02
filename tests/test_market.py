"""T1.1 RED: MarketState + default_for_platform."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.domain.enums import Console, Platform
from htop_tycoon.engine.market import (
    CONSOLE_POPULARITY,
    DEFAULT_TREND,
    PLATFORM_POPULARITY,
    MarketState,
)


def test_default_for_pc() -> None:
    m = MarketState.default_for_platform(Platform.PC)
    assert m.platform == Platform.PC
    assert m.console is None
    assert m.popularity == PLATFORM_POPULARITY[Platform.PC]
    assert m.trend == DEFAULT_TREND


def test_default_for_mobile() -> None:
    m = MarketState.default_for_platform(Platform.MOBILE)
    assert m.platform == Platform.MOBILE
    assert m.popularity == PLATFORM_POPULARITY[Platform.MOBILE]


def test_default_for_handheld() -> None:
    m = MarketState.default_for_platform(Platform.HANDHELD)
    assert m.platform == Platform.HANDHELD
    assert m.popularity == PLATFORM_POPULARITY[Platform.HANDHELD]


def test_default_for_console_uses_nova() -> None:
    """CONSOLE platform defaults to NOVA console with console-popularity."""
    m = MarketState.default_for_platform(Platform.CONSOLE)
    assert m.platform == Platform.CONSOLE
    assert m.console == Console.NOVA
    assert m.popularity == CONSOLE_POPULARITY[Console.NOVA]


def test_console_pc_uses_console_popularity_not_platform_pc() -> None:
    """Console.PC and Platform.PC must look up different popularity."""
    m_console = MarketState(console=Console.PC, platform=Platform.PC, popularity=1.0, trend=1.0)
    m_platform = MarketState.default_for_platform(Platform.PC)
    assert m_console.popularity == CONSOLE_POPULARITY[Console.PC]
    assert m_platform.popularity == PLATFORM_POPULARITY[Platform.PC]


def test_market_state_frozen() -> None:
    m = MarketState.default_for_platform(Platform.PC)
    with pytest.raises(FrozenInstanceError):
        m.popularity = 2.0  # type: ignore[misc]


def test_market_state_rejects_zero_popularity() -> None:
    with pytest.raises(ValueError):
        MarketState(console=None, platform=Platform.PC, popularity=0.0, trend=1.0)


def test_market_state_rejects_zero_trend() -> None:
    with pytest.raises(ValueError):
        MarketState(console=None, platform=Platform.PC, popularity=1.0, trend=0.0)


def test_market_state_rejects_non_numeric_popularity() -> None:
    with pytest.raises(TypeError):
        MarketState(
            console=None,
            platform=Platform.PC,
            popularity="hot",  # type: ignore[arg-type]
            trend=1.0,
        )
