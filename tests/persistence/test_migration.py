"""T5 RED: persistence version guard."""

from __future__ import annotations

import pytest

from htop_tycoon.persistence.serialize import (
    PersistenceVersionError,
    from_yaml,
    to_yaml,
)
from htop_tycoon.ui.mock_state import mock_state


def test_emitted_yaml_has_version_field() -> None:
    state = mock_state()
    text = to_yaml(state)
    assert "version:" in text
    assert "version: 2" in text


def test_missing_version_field_raises() -> None:
    with pytest.raises(PersistenceVersionError):
        from_yaml("state:\n  year: 1\n")


def test_future_version_raises() -> None:
    with pytest.raises(PersistenceVersionError):
        from_yaml("version: 99\nstate:\n  year: 1\n")


def test_roundtrip_preserves_version() -> None:
    state = mock_state()
    restored = from_yaml(to_yaml(state))
    text_again = to_yaml(restored)
    assert "version: 2" in text_again
