"""Domain enums: locked shapes for jobs, genres, platforms, consoles, departments, satisfaction tiers, strategy kinds."""

from __future__ import annotations

from enum import StrEnum


class Job(StrEnum):
    JUNIOR = "JUNIOR"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    ARTIST = "ARTIST"
    DESIGNER = "DESIGNER"
    SOUND_ENGINEER = "SOUND_ENGINEER"
    PRODUCER = "PRODUCER"
    QA = "QA"


class Genre(StrEnum):
    ACTION = "ACTION"
    RPG = "RPG"
    ADVENTURE = "ADVENTURE"
    SIMULATION = "SIMULATION"
    PUZZLE = "PUZZLE"
    STRATEGY = "STRATEGY"
    SPORTS = "SPORTS"
    HORROR = "HORROR"
    CASUAL = "CASUAL"


class Platform(StrEnum):
    PC = "PC"
    MOBILE = "MOBILE"
    CONSOLE = "CONSOLE"
    HANDHELD = "HANDHELD"


class Console(StrEnum):
    """Distinct from Platform.PC — Console represents a specific hardware vendor."""

    PC = "PC"
    GENESIS_X = "GENESIS_X"
    NOVA = "NOVA"
    PIXEL_2 = "PIXEL_2"
    ARCADE = "ARCADE"
    ATARI_Q = "ATARI_Q"


class Department(StrEnum):
    DEV = "DEV"
    ART = "ART"
    SOUND = "SOUND"
    QA = "QA"


class SatisfactionTier(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class StrategyKind(StrEnum):
    AGGRESSIVE = "AGGRESSIVE"
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    GENRE_FOCUS = "GENRE_FOCUS"
