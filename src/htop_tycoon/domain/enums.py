"""htop-tycoon v3.0 — pure-domain enumerations and ActionKind literal.

Size note: allow SIZE_OK — pure-data-table file. Each enum class is a
declaration plus 1-4 immutable lookup dicts (Korean/English labels,
priorities, royalty rates, quality contributions). There is no logic to
extract; splitting would separate the JobType table from the
JOBS_BY_DEPARTMENT derivation, or scatter the per-enum label maps across
multiple files. The dicts ARE the content of each enum.

Spec references:
- §1.3 Scope cap (5 depts, 6 base + 1 prestige jobs, 4 axes, 5 platforms, 5 endings)
- §2.1 Departments and jobs (dept ↔ job mapping + quality-axis contributions)
- §2.3 Platforms and consoles (5 platforms, royalty rates, license requirement)
- §1.4 The 5 endings (priority + forced-end flags)
- §3.2.1 ActionKind literal (9 action kinds)
- §4.1.1 nice_value compression algorithm

This module is pure: no I/O, no clock access, no random.* calls. The only
side-channel is `uuid.uuid4()` for ID factories (see ids.py), which uses
`os.urandom` and is independent of the gameplay RNG (GameRNG).

Invariant: no `import random` / `from random` anywhere in this module
(enforced by tests/test_rng.py::test_no_bare_random_import_outside_rng).
"""
from __future__ import annotations

from enum import IntEnum, auto
from typing import Final, Literal, TypeAlias

# ---------------------------------------------------------------------------
# ActionKind — typing.Literal with 9 valid values per spec §3.2.1.
# ---------------------------------------------------------------------------

ActionKind: TypeAlias = Literal[
    "HIRE",
    "FIRE",
    "TRAIN",
    "START_GAME",
    "ASSIGN",
    "PROMOTE",
    "DEMOTE",
    "CHANGE_JOB",
    "NOTHING",
]
"""Closed set of action kinds a Strategy may emit. See spec §3.2.1."""


# ---------------------------------------------------------------------------
# Department — 5 members, IntEnum for deterministic int-valued order.
# ---------------------------------------------------------------------------

class Department(IntEnum):
    """The 5 company departments. Spec §1.3, §2.1."""

    MANAGEMENT = auto()
    PLANNING = auto()
    DEVELOPMENT = auto()
    ART = auto()
    SOUND = auto()

    @property
    def ko_label(self) -> str:
        """Korean UI label for the department."""
        return _DEPARTMENT_KO_LABELS[self]

    @property
    def unlocked_at_start(self) -> bool:
        """Spec §2.1: 경영 + 기획 start unlocked; the other 3 unlock mid-game."""
        return self in _DEPARTMENTS_UNLOCKED_AT_START


_DEPARTMENT_KO_LABELS: Final[dict[Department, str]] = {
    Department.MANAGEMENT: "경영",
    Department.PLANNING: "기획",
    Department.DEVELOPMENT: "개발",
    Department.ART: "아트",
    Department.SOUND: "사운드",
}

_DEPARTMENTS_UNLOCKED_AT_START: Final[frozenset[Department]] = frozenset(
    {Department.MANAGEMENT, Department.PLANNING}
)


# ---------------------------------------------------------------------------
# QualityAxis — 4 members, IntEnum for deterministic order.
# ---------------------------------------------------------------------------

class QualityAxis(IntEnum):
    """The 4 game-quality axes. Spec §1.3 (no 'tech level' axis)."""

    FUN = auto()
    GRAPHICS = auto()
    SOUND = auto()
    ORIGINALITY = auto()

    @property
    def ko_label(self) -> str:
        """Korean UI label for the axis."""
        return _QUALITY_AXIS_KO_LABELS[self]


_QUALITY_AXIS_KO_LABELS: Final[dict[QualityAxis, str]] = {
    QualityAxis.FUN: "재미",
    QualityAxis.GRAPHICS: "그래픽",
    QualityAxis.SOUND: "사운드",
    QualityAxis.ORIGINALITY: "독창성",
}


# ---------------------------------------------------------------------------
# JobType — 6 base + 1 prestige (HW_ENGINEER), IntEnum for deterministic order.
# ---------------------------------------------------------------------------

class JobType(IntEnum):
    """The 6 base job types + 1 prestige job (HW_ENGINEER). Spec §1.3, §2.1."""

    PRODUCER = auto()
    GAME_DESIGNER = auto()
    PROGRAMMER = auto()
    GRAPHIC_ARTIST = auto()
    SOUND_CREATOR = auto()
    HACKER = auto()
    HW_ENGINEER = auto()  # prestige — unlocked only after Secret ending

    @property
    def ko_label(self) -> str:
        """Korean UI label for the job."""
        return _JOB_TYPE_KO_LABELS[self]

    @property
    def is_prestige(self) -> bool:
        """True only for HW_ENGINEER (spec §2.5: post-Secret prestige job)."""
        return self is JobType.HW_ENGINEER

    @property
    def default_department(self) -> Department:
        """The department this job belongs to (spec §2.1 table)."""
        return _JOB_DEFAULT_DEPARTMENT[self]

    @property
    def quality_axis_contributions(self) -> dict[QualityAxis, float]:
        """Per-job contribution weights to each quality axis (spec §2.1).

        For Programmer/Hacker, the FUN contribution is baked in as 2.0
        (spec §2.1: "개발 ... 재미 ... 2x weight"). Producer contributes no
        quality axis — its job is to manage the company and drive fans.
        """
        return dict(_JOB_QUALITY_CONTRIBUTIONS[self])

    @property
    def job_index(self) -> int:
        """Index in the spec §4.1.1 nice_value ordering.

        The 6 base jobs map to 0..5 (Producer=0, ..., Hacker=5). HW_ENGINEER
        has no standard index — its nice value is post-Secret prestige and
        resolved by callers separately.
        """
        if self.is_prestige:
            raise ValueError(
                "HW_ENGINEER has no JOB_INDEX_ORDER slot; "
                "its nice value is resolved separately (spec §4.1.1)."
            )
        return _JOB_INDEX_ORDER[self]


_JOB_TYPE_KO_LABELS: Final[dict[JobType, str]] = {
    JobType.PRODUCER: "프로듀서",
    JobType.GAME_DESIGNER: "게임 디자이너",
    JobType.PROGRAMMER: "프로그래머",
    JobType.GRAPHIC_ARTIST: "그래픽 아티스트",
    JobType.SOUND_CREATOR: "사운드 크리에이터",
    JobType.HACKER: "해커",
    JobType.HW_ENGINEER: "HW 엔지니어",
}

_JOB_DEFAULT_DEPARTMENT: Final[dict[JobType, Department]] = {
    JobType.PRODUCER: Department.MANAGEMENT,
    JobType.GAME_DESIGNER: Department.PLANNING,
    JobType.PROGRAMMER: Department.DEVELOPMENT,
    JobType.HACKER: Department.DEVELOPMENT,
    JobType.GRAPHIC_ARTIST: Department.ART,
    JobType.SOUND_CREATOR: Department.SOUND,
    JobType.HW_ENGINEER: Department.MANAGEMENT,
}

# Spec §2.1: per-job contribution weights. Programmer/Hacker FUN = 2.0
# (2x weight baked in). Producer contributes no quality axis.
_JOB_QUALITY_CONTRIBUTIONS: Final[dict[JobType, dict[QualityAxis, float]]] = {
    JobType.PRODUCER: {},
    JobType.GAME_DESIGNER: {QualityAxis.FUN: 1.0, QualityAxis.ORIGINALITY: 1.0},
    JobType.PROGRAMMER: {QualityAxis.FUN: 2.0},
    JobType.HACKER: {QualityAxis.FUN: 2.0},
    JobType.GRAPHIC_ARTIST: {QualityAxis.GRAPHICS: 1.0},
    JobType.SOUND_CREATOR: {QualityAxis.SOUND: 1.0},
    JobType.HW_ENGINEER: {},
}

# Spec §4.1.1: Producer=0, Game Designer=1, Programmer=2, Graphic Artist=3,
# Sound Creator=4, Hacker=5. HW_ENGINEER is NOT in this mapping (prestige).
_JOB_INDEX_ORDER: Final[dict[JobType, int]] = {
    JobType.PRODUCER: 0,
    JobType.GAME_DESIGNER: 1,
    JobType.PROGRAMMER: 2,
    JobType.GRAPHIC_ARTIST: 3,
    JobType.SOUND_CREATOR: 4,
    JobType.HACKER: 5,
}

# Reverse lookup for nice_value / quality_weight helpers.
_JOB_BY_INDEX: Final[dict[int, JobType]] = {v: k for k, v in _JOB_INDEX_ORDER.items()}

# Spec §2.1: department → jobs that belong to that department.
# Producer appears in BOTH rows of §2.1 (fans via MANAGEMENT, fun/originality via
# PLANNING); producers can be hired into either department. `_JOB_DEFAULT_DEPARTMENT`
# keeps MANAGEMENT as the canonical "primary" department for serialization.
JOBS_BY_DEPARTMENT: Final[dict[Department, list[JobType]]] = {
    Department.MANAGEMENT: [JobType.PRODUCER, JobType.HW_ENGINEER],
    Department.PLANNING: [JobType.GAME_DESIGNER, JobType.PRODUCER],
    Department.DEVELOPMENT: [JobType.PROGRAMMER, JobType.HACKER],
    Department.ART: [JobType.GRAPHIC_ARTIST],
    Department.SOUND: [JobType.SOUND_CREATOR],
}


# ---------------------------------------------------------------------------
# Platform — 5 members, IntEnum.
# ---------------------------------------------------------------------------

class Platform(IntEnum):
    """The 5 game platforms. Spec §1.3, §2.3."""

    PC = auto()
    CONSOLE_A = auto()
    CONSOLE_B = auto()
    CONSOLE_C = auto()
    OWN_CONSOLE = auto()

    @property
    def ko_label(self) -> str:
        """Korean UI label for the platform."""
        return _PLATFORM_KO_LABELS[self]

    @property
    def requires_license(self) -> bool:
        """Whether the player must purchase a license to publish on this platform.

        PC and OWN_CONSOLE are royalty/license-free; the 3 third-party consoles
        require a license (spec §2.3).
        """
        return _PLATFORM_REQUIRES_LICENSE[self]

    @property
    def royalty_rate(self) -> float:
        """Publisher royalty as a fraction of revenue (0.0 to 1.0)."""
        return _PLATFORM_ROYALTY_RATE[self]


_PLATFORM_KO_LABELS: Final[dict[Platform, str]] = {
    Platform.PC: "PC",
    Platform.CONSOLE_A: "콘솔 A",
    Platform.CONSOLE_B: "콘솔 B",
    Platform.CONSOLE_C: "콘솔 C",
    Platform.OWN_CONSOLE: "자사 콘솔",
}

_PLATFORM_REQUIRES_LICENSE: Final[dict[Platform, bool]] = {
    Platform.PC: False,
    Platform.CONSOLE_A: True,
    Platform.CONSOLE_B: True,
    Platform.CONSOLE_C: True,
    Platform.OWN_CONSOLE: False,  # self — no license
}

# Spec §2.3: PC = 0%, consoles = 15%, own console = 0%.
_PLATFORM_ROYALTY_RATE: Final[dict[Platform, float]] = {
    Platform.PC: 0.0,
    Platform.CONSOLE_A: 0.15,
    Platform.CONSOLE_B: 0.15,
    Platform.CONSOLE_C: 0.15,
    Platform.OWN_CONSOLE: 0.0,
}


# ---------------------------------------------------------------------------
# EndingKind — 5 members, IntEnum.
# ---------------------------------------------------------------------------

class EndingKind(IntEnum):
    """The 5 game endings. Spec §1.3, §1.4."""

    BANKRUPTCY = auto()
    VOLUNTARY_SALE = auto()
    MEGA_HIT = auto()
    HALL_OF_FAME = auto()
    SECRET = auto()

    @property
    def ko_label(self) -> str:
        """Korean UI label for the ending."""
        return _ENDING_KO_LABELS[self]

    @property
    def en_label(self) -> str:
        """English label (used in README/docs and serialization keys)."""
        return _ENDING_EN_LABELS[self]

    @property
    def is_forced(self) -> bool:
        """True for endings that actually end the run.

        Spec §1.4: BANKRUPTCY and VOLUNTARY_SALE are forced. The others are
        'soft' achievements tracked on the Legacy Score panel.
        """
        return self in _FORCED_ENDINGS

    @property
    def priority(self) -> int:
        """Resolution order (higher = checked first).

        BANKRUPTCY > VOLUNTARY_SALE > soft endings. Spec §1.4: forced endings
        take precedence so a player doesn't miss Bankruptcy while reading
        the Hall of Fame toast.
        """
        return _ENDING_PRIORITY[self]


_ENDING_KO_LABELS: Final[dict[EndingKind, str]] = {
    EndingKind.BANKRUPTCY: "파산",
    EndingKind.VOLUNTARY_SALE: "자발적 매각",
    EndingKind.MEGA_HIT: "대박",
    EndingKind.HALL_OF_FAME: "명예의 전당",
    EndingKind.SECRET: "비밀: 자사 콘솔 + 메가히트",
}

_ENDING_EN_LABELS: Final[dict[EndingKind, str]] = {
    EndingKind.BANKRUPTCY: "Bankruptcy",
    EndingKind.VOLUNTARY_SALE: "Voluntary Sale",
    EndingKind.MEGA_HIT: "Mega Hit",
    EndingKind.HALL_OF_FAME: "Hall of Fame",
    EndingKind.SECRET: "Secret: Own Console + Mega Hit",
}

_FORCED_ENDINGS: Final[frozenset[EndingKind]] = frozenset(
    {EndingKind.BANKRUPTCY, EndingKind.VOLUNTARY_SALE}
)

# Higher priority = resolved first. Soft endings share a lower band.
_ENDING_PRIORITY: Final[dict[EndingKind, int]] = {
    EndingKind.BANKRUPTCY: 100,
    EndingKind.VOLUNTARY_SALE: 90,
    EndingKind.MEGA_HIT: 50,
    EndingKind.HALL_OF_FAME: 40,
    EndingKind.SECRET: 30,
}


# ---------------------------------------------------------------------------
# Pure functions: nice_value + quality_weight
# ---------------------------------------------------------------------------

# Spec §4.1.1 nice value range. -20 to +19 inclusive.
_NICE_VALUE_MIN: Final[int] = -20
_NICE_VALUE_MAX: Final[int] = 19


def _clamp(value: int, low: int, high: int) -> int:
    """Clamp ``value`` to the inclusive ``[low, high]`` range."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def nice_value(job_index: int, level: int) -> int:
    """Map a (job_index, level) tuple to a Unix-style nice value in [-20, +19].

    Spec §4.1.1: higher job_index + higher level = lower (more senior) nice.
    Producer Lv5 → +16 (most senior among the base 6); Hacker Lv1 → -5
    (most junior). New hires default to Programmer Lv1 → +10.

    Args:
        job_index: 0..5, where 0=Producer, 1=Game Designer, 2=Programmer,
            3=Graphic Artist, 4=Sound Creator, 5=Hacker (spec §4.1.1).
        level: 1..5 inclusive.

    Returns:
        An integer in [-20, +19].

    Raises:
        ValueError: If job_index is outside 0..5 or level is outside 1..5.
    """
    if not 0 <= job_index <= 5:
        raise ValueError(f"job_index must be in 0..5 (spec §4.1.1); got {job_index}")
    if not 1 <= level <= 5:
        raise ValueError(f"level must be in 1..5 (spec §2.5); got {level}")
    rank = job_index * 5 + (level - 1)  # 0..29
    return _clamp(20 - rank, _NICE_VALUE_MIN, _NICE_VALUE_MAX)


def quality_weight(job_index: int, level: int, axis: QualityAxis) -> float:
    """Compute the quality-axis contribution for a (job_index, level, axis) tuple.

    Spec §2.1 + §2.5: base weight comes from the job's contribution table;
    level applies a +20% multiplier per level above 1
    (level 1 = 1.0×, level 2 = 1.2×, ..., level 5 = 1.8×).

    Args:
        job_index: 0..5 (see :func:`nice_value` for the mapping).
        level: 1..5 inclusive.
        axis: The quality axis to query.

    Returns:
        Contribution weight as a float. Returns 0.0 for axis the job does
        not contribute to, and for HW_ENGINEER (which has no standard
        job_index slot — its contribution is empty).

    Raises:
        ValueError: If job_index is outside 0..5 or level is outside 1..5.
    """
    job = _JOB_BY_INDEX.get(job_index)
    if job is None:
        # job_index out of range OR HW_ENGINEER (no slot).
        # Validate inputs (so callers get a clear error vs silent 0.0).
        if not 0 <= job_index <= 5:
            raise ValueError(f"job_index must be in 0..5 (spec §4.1.1); got {job_index}")
        if not 1 <= level <= 5:
            raise ValueError(f"level must be in 1..5 (spec §2.5); got {level}")
        return 0.0
    # Re-validate level even when job lookup succeeded (defensive; cheap).
    if not 1 <= level <= 5:
        raise ValueError(f"level must be in 1..5 (spec §2.5); got {level}")
    base = job.quality_axis_contributions.get(axis, 0.0)
    level_mult = 1.0 + 0.2 * (level - 1)  # 1.0, 1.2, 1.4, 1.6, 1.8
    return base * level_mult


__all__ = [
    "ActionKind",
    "Department",
    "EndingKind",
    "JobType",
    "JOBS_BY_DEPARTMENT",
    "Platform",
    "QualityAxis",
    "nice_value",
    "quality_weight",
]
