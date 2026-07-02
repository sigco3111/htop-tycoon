"""v3.1: production startup defaults to auto_on=True (watcher mode)."""

from __future__ import annotations

from htop_tycoon.domain import CompanyState
from htop_tycoon.ui.mock_state import mock_state


def test_company_state_default_auto_on_false() -> None:
    """Domain default: auto_on=False (test isolation, manual mode)."""
    assert CompanyState().auto_on is False


def test_mock_state_default_auto_on_false() -> None:
    """Mock state default: auto_on=False for test isolation."""
    assert mock_state(speed=0).auto_on is False


def test_toggle_auto_flips_state() -> None:
    """Toggle transitions both directions."""
    state = mock_state(speed=0)
    assert state.auto_on is False
    state = state.toggle_auto()
    assert state.auto_on is True
    state = state.toggle_auto()
    assert state.auto_on is False


def test_production_startup_pattern_auto_on_true() -> None:
    """Production pattern: mock_state + toggle_auto = auto_on=True.

    This mirrors the change in __main__.py:88:
        state = mock_state(speed=args.speed).toggle_auto()
    """
    state = mock_state(speed=1).toggle_auto()
    assert state.auto_on is True
    assert state.speed == 1