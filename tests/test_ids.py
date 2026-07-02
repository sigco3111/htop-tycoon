"""T1.2 RED: branded IDs + validated GameTitle."""

from __future__ import annotations

import pytest

from htop_tycoon.domain.ids import CompanyId, EmployeeId, GameTitle, ProjectId


def test_employee_id_is_int_subclass() -> None:
    assert isinstance(EmployeeId(5), int)


def test_employee_id_equality_with_int() -> None:
    assert EmployeeId(5) == 5
    assert EmployeeId(5) == EmployeeId(5)


def test_employee_id_distinct_per_type() -> None:
    """Same int value, different types — branding preserves identity."""
    assert EmployeeId(5) != ProjectId(5)
    assert EmployeeId(5) != CompanyId(5)


def test_ids_hashable_for_dict_keys() -> None:
    mapping: dict[EmployeeId, str] = {EmployeeId(1): "Ada"}
    assert mapping[EmployeeId(1)] == "Ada"


def test_game_title_rejects_empty() -> None:
    with pytest.raises(ValueError):
        GameTitle("")


def test_game_title_rejects_whitespace_only() -> None:
    with pytest.raises(ValueError):
        GameTitle("   ")
    with pytest.raises(ValueError):
        GameTitle("\t\n")


def test_game_title_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        GameTitle(123)  # type: ignore[arg-type]


def test_game_title_strips_whitespace() -> None:
    assert str(GameTitle("  Eldritch Quest  ")) == "Eldritch Quest"


def test_game_title_accepts_normal() -> None:
    assert str(GameTitle("Eldritch Quest")) == "Eldritch Quest"
