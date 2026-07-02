"""T1.1 RED: enums locked shape — 8 jobs in documented order, distinct identities, 4 strategies, etc."""

from __future__ import annotations

from htop_tycoon.domain.enums import (
    Console,
    Department,
    Genre,
    Job,
    Platform,
    SatisfactionTier,
    StrategyKind,
)


def test_job_has_eight_members_in_documented_order() -> None:
    assert [m.name for m in Job] == [
        "JUNIOR",
        "SENIOR",
        "LEAD",
        "ARTIST",
        "DESIGNER",
        "SOUND_ENGINEER",
        "PRODUCER",
        "QA",
    ]


def test_enum_values_are_uppercase_strings() -> None:
    assert Genre.ACTION.value == "ACTION"
    assert isinstance(Genre.ACTION.value, str)
    assert Job.LEAD.value == "LEAD"


def test_console_pc_distinct_from_platform_pc() -> None:
    """Console.PC and Platform.PC are different enum classes (different roles).

    They share the same string value 'PC' but belong to distinct StrEnum
    classes — the test asserts isinstance membership, not value equality.
    """
    assert isinstance(Console.PC, Console)
    assert isinstance(Platform.PC, Platform)
    assert not isinstance(Console.PC, Platform)
    assert not isinstance(Platform.PC, Console)
    console_pc_type: type = type(Console.PC)
    platform_pc_type: type = type(Platform.PC)
    assert console_pc_type is not platform_pc_type


def test_satisfaction_tier_three_members() -> None:
    assert {m.name for m in SatisfactionTier} == {"GREEN", "YELLOW", "RED"}


def test_strategy_kind_four_members() -> None:
    assert {m.name for m in StrategyKind} == {
        "AGGRESSIVE",
        "CONSERVATIVE",
        "BALANCED",
        "GENRE_FOCUS",
    }


def test_department_four_members() -> None:
    assert {m.name for m in Department} == {"DEV", "ART", "SOUND", "QA"}


def test_genre_has_nine_members() -> None:
    assert len(list(Genre)) == 9


def test_platform_has_four_members() -> None:
    assert {m.name for m in Platform} == {"PC", "MOBILE", "CONSOLE", "HANDHELD"}


def test_enums_are_str_subclasses_for_serialization() -> None:
    """StrEnum members serialize as plain strings — required for YAML/JSON round-trips."""
    assert Genre.ACTION == "ACTION"
    assert Job.LEAD == "LEAD"
    assert f"{Genre.RPG}" == "RPG"
