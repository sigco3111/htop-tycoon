"""htop-tycoon v3.0 — Strategy dispatch + Registry bootstrapper.

Per spec §3.2.3 file layout:
    src/htop_tycoon/engine/strategy/
    ├── __init__.py   # exports StrategyRegistry (this module)
    ├── types.py
    ├── base.py
    ├── aggressive.py
    ├── conservative.py
    ├── balanced.py
    └── genre_focus.py
"""
from __future__ import annotations

from htop_tycoon.engine.strategy.aggressive import AggressiveStrategy
from htop_tycoon.engine.strategy.balanced import BalancedStrategy
from htop_tycoon.engine.strategy.base import Strategy, StrategyRegistry
from htop_tycoon.engine.strategy.conservative import ConservativeStrategy
from htop_tycoon.engine.strategy.dispatch import dispatch_action
from htop_tycoon.engine.strategy.genre_focus import GenreFocusStrategy
from htop_tycoon.engine.strategy.types import ActionKind, PlannedAction


def register_default_strategies() -> None:
    """Idempotent: register the 4 default strategies.

    Call this once at app boot (the UI layer does this in Wave 6+). Safe
    to call multiple times — the registry raises on duplicate names, so
    we guard with a try/except for forward-compat with future
    hot-reloading scenarios.
    """
    defaults: list[tuple[str, type[Strategy]]] = [
        ("aggressive", AggressiveStrategy),
        ("conservative", ConservativeStrategy),
        ("balanced", BalancedStrategy),
        ("genre_focus", GenreFocusStrategy),
    ]
    for name, cls in defaults:
        if name in StrategyRegistry._registry:
            continue
        StrategyRegistry.register(name, cls)


def get_strategy(name: str) -> Strategy:
    """Return an instance of the named strategy. Spec §3.2.3."""
    return StrategyRegistry.get(name)


__all__ = [
    "ActionKind",
    "AggressiveStrategy",
    "BalancedStrategy",
    "ConservativeStrategy",
    "GenreFocusStrategy",
    "PlannedAction",
    "Strategy",
    "StrategyRegistry",
    "dispatch_action",
    "get_strategy",
    "register_default_strategies",
]
