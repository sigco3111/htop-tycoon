"""T4.1 RED: engine barrel — every public type must re-export cleanly."""

from __future__ import annotations

import pytest

EXPECTED_PUBLIC_TYPES: tuple[str, ...] = (
    # market
    "MarketState",
    # productivity
    "compute_employee_productivity",
    # game_dev
    "compute_daily_progress",
    "advance_projects",
    # sales
    "compute_sales_revenue",
    # tick
    "tick",
)


def test_reexports_all_public_types() -> None:
    import htop_tycoon.engine as eng

    for name in EXPECTED_PUBLIC_TYPES:
        assert hasattr(eng, name), f"htop_tycoon.engine.{name} not re-exported"


def test_reexports_are_callable() -> None:
    """Functions are callable; classes are types."""
    from htop_tycoon.engine import (
        MarketState,
        advance_projects,
        compute_daily_progress,
        compute_employee_productivity,
        compute_sales_revenue,
        tick,
    )

    assert callable(tick)
    assert callable(compute_daily_progress)
    assert callable(advance_projects)
    assert callable(compute_sales_revenue)
    assert callable(compute_employee_productivity)
    assert isinstance(MarketState, type)


def test_no_internals_leaked() -> None:
    """Internal helpers must NOT be re-exported."""
    with pytest.raises(ImportError):
        from htop_tycoon.engine import (  # type: ignore[attr-defined]  # noqa: F401
            _drift_satisfaction_for_all,
        )


def test_all_exports_listed_in_all() -> None:
    import htop_tycoon.engine as eng

    assert hasattr(eng, "__all__"), "htop_tycoon.engine must define __all__"
    missing = set(EXPECTED_PUBLIC_TYPES) - set(eng.__all__)
    assert not missing, f"Public types missing from __all__: {missing}"


def test_engine_does_not_import_textual() -> None:
    """Engine layer must never touch the UI."""
    import ast
    import pathlib

    engine_dir = pathlib.Path("src/htop_tycoon/engine")
    textual_imports: list[str] = []
    for py_file in engine_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "textual" in alias.name:
                        textual_imports.append(f"{py_file}: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and "textual" in node.module:
                    textual_imports.append(f"{py_file}: {node.module}")
    assert not textual_imports, f"Engine must not import textual: {textual_imports}"
