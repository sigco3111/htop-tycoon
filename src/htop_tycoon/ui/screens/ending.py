"""EndingScreen (modal) + LegacyPanel (body widget) — Phase 2G.

EndingScreen is shown when a HARD ending fires (BANKRUPTCY, VOLUNTARY_SALE).
It pauses the timer and offers New Game / Quit actions.

LegacyPanel is mounted in the body and renders the all-time list of
soft endings (MEGA_HIT, HALL_OF_FAME, SECRET, plus historical BANKRUPTCY
+ VOLUNTARY_SALE rows).
"""

from __future__ import annotations

from htop_tycoon.domain.money import Money
from htop_tycoon.engine.endings import (
    ENDING_DESCRIPTIONS,
    ENDING_LABELS,
    Ending,
    EndingKind,
    LegacyScore,
)

__all__ = [
    "EndingScreen",
    "LegacyPanel",
    "ENDING_LABELS",
    "ENDING_DESCRIPTIONS",
]


def _format_legacy_line(score: LegacyScore) -> str:
    cash = Money(score.ending_cash_cents)
    return (
        f"{score.ending_kind.value} · Year {score.ending_year} · "
        f"Cash {cash} · Fans {score.total_fans:,} · "
        f"Games {score.games_shipped} · Mega {score.mega_hits}"
    )


class LegacyPanel:
    """Body widget showing all-time legacy scores.

    Pure data holder — render() returns the multi-line string used by
    App. App.mount()'s LegacyPanel under the #body Vertical.
    """

    __slots__ = ("_scores",)

    def __init__(self, scores: tuple[LegacyScore, ...] | list[LegacyScore]) -> None:
        self._scores: tuple[LegacyScore, ...] = tuple(scores)

    @property
    def scores(self) -> tuple[LegacyScore, ...]:
        return self._scores

    def render(self) -> str:
        if not self._scores:
            return "Legacy (no endings yet)"
        lines = [f"Legacy ({len(self._scores)})"]
        for score in self._scores:
            lines.append(f"  {_format_legacy_line(score)}")
        return "\n".join(lines)


class EndingScreen:
    """Modal data describing an ending. App.push_screen wraps this.

    In Phase 2G we keep the modal as a pure-data holder and let the
    App.render it via its own screen. Full Textual ModalScreen subclass
    with BINDINGS arrives in a follow-up phase.
    """

    __slots__ = ("_ending", "_legacy")

    def __init__(self, ending: Ending, legacy: LegacyScore) -> None:
        self._ending = ending
        self._legacy = legacy

    @property
    def ending(self) -> Ending:
        return self._ending

    @property
    def legacy(self) -> LegacyScore:
        return self._legacy

    def render(self) -> str:
        label = ENDING_LABELS.get(self._ending.kind, self._ending.kind.value)
        cash = Money(self._legacy.ending_cash_cents)
        return (
            f"=== {label} ===\n"
            f"Year {self._legacy.ending_year}\n"
            f"Cash: {cash}\n"
            f"Fans: {self._legacy.total_fans:,}\n"
            f"Games Shipped: {self._legacy.games_shipped}\n"
            f"Mega Hits: {self._legacy.mega_hits}\n"
            f"\n{self._ending.description}\n"
            f"\n[New Game]    [Quit]"
        )


# Re-export for convenience
ENDING_KIND_LABELS = ENDING_LABELS
ENDING_KIND_DESCRIPTIONS = ENDING_DESCRIPTIONS
ENDING_VALUES: tuple[str, ...] = tuple(k.value for k in EndingKind)
