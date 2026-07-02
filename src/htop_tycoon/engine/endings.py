"""Endings: detection logic + legacy score construction + idempotent recording.

Phase 2G. detect_ending has priority cascade (BANKRUPTCY > VOLUNTARY_SALE
> MEGA_HIT > HALL_OF_FAME > SECRET). Soft endings (3, 4, 5) record to
state.legacy_scores without pausing the game.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from htop_tycoon.domain.state import CompanyState


class EndingKind(StrEnum):
    BANKRUPTCY = "BANKRUPTCY"
    VOLUNTARY_SALE = "VOLUNTARY_SALE"
    MEGA_HIT = "MEGA_HIT"
    HALL_OF_FAME = "HALL_OF_FAME"
    SECRET = "SECRET"


HARD_ENDINGS: frozenset[EndingKind] = frozenset(
    {EndingKind.BANKRUPTCY, EndingKind.VOLUNTARY_SALE}
)

ENDING_LABELS: dict[EndingKind, str] = {
    EndingKind.BANKRUPTCY: "Bankruptcy",
    EndingKind.VOLUNTARY_SALE: "Voluntary Sale",
    EndingKind.MEGA_HIT: "Mega Hit",
    EndingKind.HALL_OF_FAME: "Hall of Fame",
    EndingKind.SECRET: "Secret Ending",
}

ENDING_LABELS_KO: dict[EndingKind, str] = {
    EndingKind.BANKRUPTCY: "파산",
    EndingKind.VOLUNTARY_SALE: "자발적 매각",
    EndingKind.MEGA_HIT: "대박",
    EndingKind.HALL_OF_FAME: "명예의 전당",
    EndingKind.SECRET: "비밀 엔딩",
}

ENDING_DESCRIPTIONS: dict[EndingKind, str] = {
    EndingKind.BANKRUPTCY: "Your company went bankrupt.",
    EndingKind.VOLUNTARY_SALE: "You sold the studio on your own terms.",
    EndingKind.MEGA_HIT: "One of your games sold over 1 million copies!",
    EndingKind.HALL_OF_FAME: "Five or more games entered the Hall of Fame.",
    EndingKind.SECRET: "Your console launched a million-seller title.",
}

ENDING_DESCRIPTIONS_KO: dict[EndingKind, str] = {
    EndingKind.BANKRUPTCY: "회사가 파산했습니다.",
    EndingKind.VOLUNTARY_SALE: "스튜디오를 자발적으로 매각했습니다.",
    EndingKind.MEGA_HIT: "단일 게임이 100만 장 이상 판매되었습니다!",
    EndingKind.HALL_OF_FAME: "5개 이상의 게임이 명예의 전당에 입성했습니다.",
    EndingKind.SECRET: "자사 콘솔에서 100만 판매를 달성했습니다!",
}

BANKRUPTCY_THRESHOLD_CENTS: int = -50_000_00
VOLUNTARY_SALE_MIN_CENTS: int = 200_000_00
MEGA_HIT_UNITS: int = 1_000_000
HALL_OF_FAME_REQUIRED: int = 5


@dataclass(frozen=True, slots=True)
class Ending:
    kind: EndingKind
    triggered_at: tuple[int, int]
    description: str


@dataclass(frozen=True, slots=True)
class LegacyScore:
    ending_kind: EndingKind
    ending_year: int
    ending_cash_cents: int
    total_fans: int
    games_shipped: int
    mega_hits: int


def detect_ending(state: CompanyState) -> Ending | None:
    """Return the highest-priority ending condition triggered, or None.

    Priority cascade: hard endings (BANKRUPTCY, VOLUNTARY_SALE) first,
    then soft endings in specificity order (SECRET > MEGA_HIT > HALL_OF_FAME).
    """
    if state.cash.cents < BANKRUPTCY_THRESHOLD_CENTS:
        return Ending(
            kind=EndingKind.BANKRUPTCY,
            triggered_at=(state.year, state.day_index),
            description=ENDING_DESCRIPTIONS[EndingKind.BANKRUPTCY],
        )
    if state.voluntary_sale_pending and state.cash.cents >= VOLUNTARY_SALE_MIN_CENTS:
        return Ending(
            kind=EndingKind.VOLUNTARY_SALE,
            triggered_at=(state.year, state.day_index),
            description=ENDING_DESCRIPTIONS[EndingKind.VOLUNTARY_SALE],
        )
    if state.own_console is not None and any(
        p.console == state.own_console and p.units_sold >= MEGA_HIT_UNITS
        for p in state.projects.values()
    ):
        return Ending(
            kind=EndingKind.SECRET,
            triggered_at=(state.year, state.day_index),
            description=ENDING_DESCRIPTIONS[EndingKind.SECRET],
        )
    if any(p.units_sold >= MEGA_HIT_UNITS for p in state.projects.values()):
        return Ending(
            kind=EndingKind.MEGA_HIT,
            triggered_at=(state.year, state.day_index),
            description=ENDING_DESCRIPTIONS[EndingKind.MEGA_HIT],
        )
    if (
        sum(1 for p in state.projects.values() if p.hall_of_fame)
        >= HALL_OF_FAME_REQUIRED
    ):
        return Ending(
            kind=EndingKind.HALL_OF_FAME,
            triggered_at=(state.year, state.day_index),
            description=ENDING_DESCRIPTIONS[EndingKind.HALL_OF_FAME],
        )
    return None


def construct_legacy_score(state: CompanyState, ending: Ending) -> LegacyScore:
    """Snapshot current state metrics for the legacy panel."""
    return LegacyScore(
        ending_kind=ending.kind,
        ending_year=ending.triggered_at[0],
        ending_cash_cents=state.cash.cents,
        total_fans=state.fans,
        games_shipped=state.games_shipped,
        mega_hits=state.mega_hits,
    )


def record_ending(state: CompanyState, ending: Ending) -> CompanyState:
    """Append ending to state.legacy_scores, idempotent per kind.

    If the last recorded ending is the same kind, skip (prevents duplicates
    when the same condition persists across multiple ticks).
    """
    score = construct_legacy_score(state, ending)
    last = state.legacy_scores[-1] if state.legacy_scores else None
    if last is not None and getattr(last, "ending_kind", None) == ending.kind:
        return state
    return state.append_legacy_score(score)
