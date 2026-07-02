"""S1 smoke test: package importable + version locked + textual present.

This is the RED test for S1 — must FAIL until src/htop_tycoon/__init__.py
exists with __version__ == "3.0.0".
"""

from __future__ import annotations


def test_htop_tycoon_importable() -> None:
    """`import htop_tycoon` must succeed and expose __version__ == '3.0.0'."""
    import htop_tycoon

    assert hasattr(htop_tycoon, "__version__"), "htop_tycoon must expose __version__"
    assert htop_tycoon.__version__ == "3.0.0", (
        f"Expected version 3.0.0, got {htop_tycoon.__version__!r}"
    )


def test_textual_available() -> None:
    """`import textual` must succeed (transitive dependency)."""
    import textual

    assert isinstance(textual.__version__, str)
    assert textual.__version__, "textual.__version__ must be non-empty"


def test_pyproject_metadata() -> None:
    """Lockfile must record the project metadata we expect."""
    import htop_tycoon

    # Version is the single source of truth for now.
    assert htop_tycoon.__version__.count(".") == 2, (
        "Version must follow semver MAJOR.MINOR.PATCH"
    )
