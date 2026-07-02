"""T1.4 RED: QualityAxes (0..100 clamp + sum) + Progress (0..100 + is_complete)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from htop_tycoon.domain.quality import Progress, QualityAxes


def test_quality_axes_clamps_negative() -> None:
    assert QualityAxes(-5, 50, 50, 50).fun == 0


def test_quality_axes_clamps_over_100() -> None:
    """Each axis clamps independently — only fun is over 100, others stay."""
    q = QualityAxes(150, 200, 50, 50)
    assert q.fun == 100
    assert q.graphics == 100
    assert q.sound == 50
    assert q.originality == 50


def test_quality_axes_default_zero() -> None:
    assert QualityAxes() == QualityAxes(0, 0, 0, 0)


def test_quality_axes_sum() -> None:
    assert QualityAxes(80, 70, 60, 50).sum() == 260


def test_quality_axes_sum_max() -> None:
    assert QualityAxes(100, 100, 100, 100).sum() == 400


def test_quality_axes_equality() -> None:
    assert QualityAxes(50, 50, 50, 50) == QualityAxes(50, 50, 50, 50)


def test_quality_axes_hashable() -> None:
    s = {QualityAxes(50, 50, 50, 50), QualityAxes(50, 50, 50, 50)}
    assert len(s) == 1


def test_quality_axes_frozen() -> None:
    q = QualityAxes(1, 1, 1, 1)
    with pytest.raises(FrozenInstanceError):
        q.fun = 2  # type: ignore[misc]


def test_progress_clamps_negative() -> None:
    assert Progress(-5).value == 0


def test_progress_clamps_over_100() -> None:
    assert Progress(150).value == 100


def test_progress_default_zero() -> None:
    assert Progress().value == 0


def test_progress_is_complete_at_100() -> None:
    assert Progress(100).is_complete is True


def test_progress_not_complete_below_100() -> None:
    assert Progress(99).is_complete is False
    assert Progress(0).is_complete is False


def test_progress_with_increment_clamps() -> None:
    assert Progress(80).with_increment(50).value == 100


def test_progress_with_increment_normal() -> None:
    assert Progress(50).with_increment(25).value == 75


def test_progress_with_increment_returns_new_instance() -> None:
    """Frozen — must return new Progress, not mutate."""
    p = Progress(50)
    p2 = p.with_increment(10)
    assert p.value == 50
    assert p2.value == 60


def test_progress_frozen() -> None:
    p = Progress(50)
    with pytest.raises(FrozenInstanceError):
        p.value = 60  # type: ignore[misc]
