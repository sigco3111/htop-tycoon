"""StrategyPicker — modal screen for selecting one of 4 strategies.

Phase 2H. Pure data holder (mirrors EndingScreen pattern); renders
text with arrow markers + numbered list. Selection returns the picked
StrategyKind; App applies it to state.
"""

from __future__ import annotations

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.engine.strategy import STRATEGY_REGISTRY

STRATEGY_DESCRIPTIONS: dict[StrategyKind, str] = {
    StrategyKind.AGGRESSIVE: "Hire fast, big projects, take risks",
    StrategyKind.CONSERVATIVE: "Slow & steady; cut losses when cash is low",
    StrategyKind.BALANCED: "Moderate hiring, mixed project sizes",
    StrategyKind.GENRE_FOCUS: "Concentrate resources on a single genre",
}


class StrategyPicker:
    """Modal data holder for strategy selection.

    render() returns formatted text with arrow marker for current.
    select(kind) returns the picked StrategyKind (no side effect).
    """

    __slots__ = ("_current",)

    def __init__(self, current: StrategyKind) -> None:
        self._current = current

    @property
    def current(self) -> StrategyKind:
        return self._current

    def render(self) -> str:
        all_kinds = list(StrategyKind)
        lines = [
            f"Strategy: → {STRATEGY_REGISTRY[self._current.value]().name} ←",
            "",
        ]
        for idx, kind in enumerate(all_kinds, start=1):
            name = STRATEGY_REGISTRY[kind.value]().name
            desc = STRATEGY_DESCRIPTIONS[kind]
            lines.append(f"{idx}. {name:<14} - {desc}")
        lines.append("")
        lines.append("Press 1-4 to select, 's' to close, 'esc' to cancel.")
        return "\n".join(lines)

    def select(self, kind: StrategyKind) -> StrategyKind:
        return kind
