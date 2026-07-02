"""T3: ending types — EndingKind, Ending, LegacyScore."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.engine.endings import (
    HARD_ENDINGS,
    Ending,
    EndingKind,
    LegacyScore,
)


def test_ending_kind_has_five_values() -> None:
    assert {k.value for k in EndingKind} == {
        "BANKRUPTCY",
        "VOLUNTARY_SALE",
        "MEGA_HIT",
        "HALL_OF_FAME",
        "SECRET",
    }


def test_hard_endings_set() -> None:
    assert EndingKind.BANKRUPTCY in HARD_ENDINGS
    assert EndingKind.VOLUNTARY_SALE in HARD_ENDINGS
    assert EndingKind.MEGA_HIT not in HARD_ENDINGS
    assert EndingKind.HALL_OF_FAME not in HARD_ENDINGS
    assert EndingKind.SECRET not in HARD_ENDINGS


def test_ending_is_frozen() -> None:
    ending = Ending(
        kind=EndingKind.BANKRUPTCY,
        triggered_at=(1, 5),
        description="broke",
    )
    assert ending.kind == EndingKind.BANKRUPTCY
    assert ending.triggered_at == (1, 5)
    assert ending.description == "broke"
    with pytest.raises(FrozenInstanceError):
        ending.description = "fixed"  # type: ignore[misc]


def test_legacy_score_frozen() -> None:
    score = LegacyScore(
        ending_kind=EndingKind.MEGA_HIT,
        ending_year=3,
        ending_cash_cents=250_000_00,
        total_fans=5000,
        games_shipped=12,
        mega_hits=2,
    )
    assert score.ending_kind == EndingKind.MEGA_HIT
    assert score.ending_year == 3
    assert score.ending_cash_cents == 250_000_00
    assert score.total_fans == 5000
    assert score.games_shipped == 12
    assert score.mega_hits == 2
    with pytest.raises(FrozenInstanceError):
        score.ending_year = 99  # type: ignore[misc]
