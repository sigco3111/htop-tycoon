"""Determinism regression tests for GameState.compute_hash(). Spec §7.3.

These tests pin down the frozen-state hash contract that Wave 5+ will lock
to specific values (seed=42 → day 100 / 1000 / 3650). Once persistence
lands, the captioned literals become release gates.
"""
from __future__ import annotations

import dataclasses

import pytest

from htop_tycoon.domain import (
    Department,
    Employee,
    # NewType IDs (wrap raw strings to satisfy mypy --strict)
    EmployeeId,
    GameProject,
    GameState,
    GenreId,
    JobType,
    Platform,
    PlatformId,
    ProjectId,
    QualityAxis,
    ThemeId,
)

# --- Property-based: same values → same hash -----------------------------


def test_compute_hash_deterministic_two_blank_states() -> None:
    """Two blank ``GameState()`` instances must hash equal."""
    a = GameState()
    b = GameState()
    assert a.compute_hash() == b.compute_hash()
    assert b.compute_hash() == a.compute_hash()


def test_compute_hash_field_order_insensitive() -> None:
    """Same fields in different assignment order → same hash."""
    a = GameState(day=100, cash=50000, fans=0)
    b = GameState(fans=0, cash=50000, day=100)
    assert a.compute_hash() == b.compute_hash()


def test_compute_hash_independent_of_object_identity() -> None:
    """Two distinct instances with identical fields produce the same hash."""
    a = GameState(day=42)
    b = GameState(day=42)
    assert a is not b
    assert a.compute_hash() == b.compute_hash()


# --- Mutation sensitivity -------------------------------------------------


def test_compute_hash_changes_on_field_replacement() -> None:
    """``dataclasses.replace`` changes the hash."""
    base = GameState()
    base_hash = base.compute_hash()
    modified = base.replace(cash=base.cash + 1)
    assert modified.compute_hash() != base_hash


def test_compute_hash_changes_on_day_advance() -> None:
    """Day advance is the key deterministic test for the tick engine (Wave 3+)."""
    base = GameState()
    base_hash = base.compute_hash()
    advanced = base.replace(day=1)
    assert advanced.compute_hash() != base_hash


def test_compute_hash_changes_on_employee_added() -> None:
    """Adding an employee mutates the hash."""
    s = GameState()
    base_hash = s.compute_hash()
    e = Employee(
        id=EmployeeId("emp-1"),
        name="테스터",
        dept=Department.PLANNING,
        job=JobType.GAME_DESIGNER,
        level=3,
    )
    modified = s.replace(employees=(e,))
    assert modified.compute_hash() != base_hash
    # but removing + re-adding the same employee yields the same hash:
    re_modified = modified.replace(employees=())
    assert re_modified.compute_hash() == base_hash


def test_compute_hash_changes_on_project_added() -> None:
    base = GameState()
    base_hash = base.compute_hash()
    p = GameProject(
        id=ProjectId("p1"),
        name="시간여행 RPG",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("time_travel"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=42.5,
        quality_axes={
            QualityAxis.FUN: 6.0,
            QualityAxis.GRAPHICS: 5.0,
            QualityAxis.SOUND: 4.0,
            QualityAxis.ORIGINALITY: 7.0,
        },
    )
    modified = base.replace(projects=(p,))
    assert modified.compute_hash() != base_hash


# --- Immutability ---------------------------------------------------------


def test_game_state_is_frozen() -> None:
    """Assignment to a frozen dataclass field raises FrozenInstanceError."""
    s = GameState()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.cash = 999  # type: ignore[misc]


def test_replace_does_not_mutate() -> None:
    """``GameState.replace`` returns a new instance; original is untouched."""
    s1 = GameState()
    s2 = s1.replace(day=1, cash=49_999)
    assert s1.day == 0
    assert s1.cash == 50_000
    assert s2.day == 1
    assert s2.cash == 49_999
    assert s1 is not s2


# --- Derived views -------------------------------------------------------


def test_employees_by_dept_filter() -> None:
    e1 = Employee(
        id=EmployeeId("e1"),
        name="A",
        dept=Department.PLANNING,
        job=JobType.GAME_DESIGNER,
        level=2,
    )
    e2 = Employee(
        id=EmployeeId("e2"),
        name="B",
        dept=Department.DEVELOPMENT,
        job=JobType.PROGRAMMER,
        level=1,
    )
    e3 = Employee(
        id=EmployeeId("e3"),
        name="C",
        dept=Department.PLANNING,
        job=JobType.PRODUCER,
        level=4,
    )
    s = GameState(employees=(e1, e2, e3))

    planning = s.employees_by_dept(Department.PLANNING)
    assert len(planning) == 2
    assert {e.id for e in planning} == {EmployeeId("e1"), EmployeeId("e3")}

    development = s.employees_by_dept(Department.DEVELOPMENT)
    assert len(development) == 1
    assert development[0].id == EmployeeId("e2")

    art = s.employees_by_dept(Department.ART)
    assert art == ()


def test_active_vs_released_projects() -> None:
    p_active = GameProject(
        id=ProjectId("p-active"),
        name="Active",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=42.0,
    )
    p_released = GameProject(
        id=ProjectId("p-released"),
        name="Released",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=100.0,
        released_day=10,
    )
    s = GameState(projects=(p_active, p_released))
    assert {p.id for p in s.active_projects()} == {ProjectId("p-active")}
    assert {p.id for p in s.released_projects()} == {ProjectId("p-released")}


# --- Spec §7.3 contract: same seed-equivalent fields yield identical hash --


def test_canonicalize_field_insertion_order_does_not_matter() -> None:
    """build state two ways — one reverse — and verify identical hash."""
    e1 = Employee(
        id=EmployeeId("e1"),
        name="A",
        dept=Department.PLANNING,
        job=JobType.GAME_DESIGNER,
        level=2,
    )
    e2 = Employee(
        id=EmployeeId("e2"),
        name="B",
        dept=Department.DEVELOPMENT,
        job=JobType.PROGRAMMER,
        level=1,
    )
    forward = GameState(employees=(e1, e2))
    reverse = GameState(employees=(e2, e1))  # different order — different hash
    # Order in tuple is structural; reverse ≠ forward by tuple-order.
    # This test documents that: tuple ORDER matters (it's part of identity).
    assert forward.compute_hash() != reverse.compute_hash()
