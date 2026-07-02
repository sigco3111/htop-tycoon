"""Tests for tick() auto_on dispatch — auto_execute vs _apply_strategy_decisions."""

from __future__ import annotations

from htop_tycoon.domain import CompanyState, Money
from htop_tycoon.domain.enums import Platform, StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine import tick
from htop_tycoon.engine.market import MarketState


def test_tick_with_auto_on_runs_pick_strategy() -> None:
    """When state.auto_on=True, tick() re-picks strategy."""
    state = CompanyState(
        cash=Money(-1_00), auto_on=True, strategy=StrategyKind.AGGRESSIVE,
    )
    market = MarketState.default_for_platform(Platform.PC)
    new_state = tick(state, GameRng(0), market)
    assert new_state.strategy == StrategyKind.CONSERVATIVE


def test_tick_with_auto_off_preserves_strategy() -> None:
    """When state.auto_on=False, tick() does NOT change strategy."""
    state = CompanyState(
        cash=Money(-1_00), auto_on=False, strategy=StrategyKind.AGGRESSIVE,
    )
    market = MarketState.default_for_platform(Platform.PC)
    new_state = tick(state, GameRng(0), market)
    assert new_state.strategy == StrategyKind.AGGRESSIVE


def test_tick_with_auto_on_hires_when_aggressive_and_rich() -> None:
    state = CompanyState(
        cash=Money(150_000_00), auto_on=True, strategy=StrategyKind.AGGRESSIVE,
    )
    market = MarketState.default_for_platform(Platform.PC)
    new_state = tick(state, GameRng(0), market)
    assert len(new_state.employees) == 1