"""Data layer for htop-tycoon: balance tunables and seed fixtures."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "time",
        "money",
        "departments",
        "employees",
        "products",
        "competitors",
        "events",
        "endings",
        "save",
    }
)

__all__ = ["REQUIRED_TOP_LEVEL_KEYS", "load_balance"]


@lru_cache(maxsize=1)
def load_balance() -> dict[str, Any]:
    """Load and parse ``balance.yaml`` from this package.

    The result is cached after the first call, so all callers receive the
    same ``dict`` object (identity-equal). This guarantees the engine,
    persistence layer, and UI all observe a single, consistent snapshot.

    Returns:
        The parsed YAML mapping, typed as ``dict[str, Any]``.

    Raises:
        FileNotFoundError: If ``balance.yaml`` is missing from the package.
        TypeError: If the YAML root is not a mapping.
        KeyError: If any required top-level key is absent.
    """
    yaml_path = Path(__file__).parent / "balance.yaml"
    with yaml_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise TypeError(
            f"balance.yaml must be a mapping at the root, got {type(data).__name__}"
        )
    missing = REQUIRED_TOP_LEVEL_KEYS - data.keys()
    if missing:
        raise KeyError(f"balance.yaml missing required top-level keys: {sorted(missing)}")
    return data
