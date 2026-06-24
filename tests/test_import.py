"""Smoke tests for T1 (project scaffold)."""

from __future__ import annotations

import importlib

import htop_tycoon


def test_htop_tycoon_imports() -> None:
    """The package import must succeed after `uv sync`."""
    assert htop_tycoon is not None


def test_htop_tycoon_version_is_string() -> None:
    """__version__ must be exposed as a string."""
    assert isinstance(htop_tycoon.__version__, str)
    # PEP 440 compliant: at least one dot, no leading 'v'
    assert "." in htop_tycoon.__version__
    assert not htop_tycoon.__version__.startswith("v")


def test_submodule_imports() -> None:
    """Top-level submodules referenced in plan must import cleanly."""
    for name in ["htop_tycoon.__main__"]:
        mod = importlib.import_module(name)
        assert mod is not None
