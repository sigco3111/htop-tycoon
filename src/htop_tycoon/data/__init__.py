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
        # Wave 7 (T36): market regimes (BOOM / NORMAL / RECESSION / CRISIS)
        # with per-regime cycle + transition weights + modifiers and the
        # ``crisis_cash_shock_amount``. Required so ``load_balance()`` fails
        # loudly at startup if the YAML drifts.
        "regimes",
    }
)

__all__ = ["REQUIRED_TOP_LEVEL_KEYS", "load_balance", "load_endings", "load_seeds"]

_SEEDS_YAML_FILENAME: str = "seeds.yaml"


@lru_cache(maxsize=1)
def load_seeds() -> dict[str, Any]:
    """Load and parse ``seeds.yaml`` from this package.

    Cached after the first call so all callers receive the same ``dict``
    object (identity-equal). Mirrors :func:`load_balance` and
    :func:`load_endings`.

    Returns:
        The parsed YAML mapping, typed as ``dict[str, Any]``. The T33
        contract requires the top-level key ``endings`` (a mapping of
        ending key -> ``{seed, expected_tick, command_line}`` fixture).

    Raises:
        FileNotFoundError: If ``seeds.yaml`` is missing from the package.
        TypeError: If the YAML root is not a mapping.
    """
    yaml_path = Path(__file__).parent / _SEEDS_YAML_FILENAME
    with yaml_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise TypeError(
            f"{_SEEDS_YAML_FILENAME} must be a mapping at the root, "
            f"got {type(data).__name__}"
        )
    return data


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


@lru_cache(maxsize=1)
def load_endings() -> dict[str, Any]:
    """Load and parse ``endings.yaml`` from this package.

    Returns the inner ``endings`` mapping (the 5 Korean ending entries).
    Cached after the first call so all callers receive the same ``dict``
    object (identity-equal). Mirror of :func:`load_balance` for the
    endings content layer; trigger-condition evaluators live in
    ``domain/ending.py`` (T8) and ``engine/ending.py`` (T15).

    Returns:
        A mapping of ending key (``BANKRUPTCY``, ``IPO``, ``HOSTILE_MA``,
        ``VOLUNTARY_SALE``, ``SECRET``) to a per-ending mapping with
        ``title_ko``, ``summary_ko``, and ``stats_labels``.

    Raises:
        FileNotFoundError: If ``endings.yaml`` is missing from the package.
        TypeError: If the YAML root or ``endings`` value is not a mapping.
    """
    yaml_path = Path(__file__).parent / "endings.yaml"
    with yaml_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise TypeError(
            f"endings.yaml must be a mapping at the root, got {type(data).__name__}"
        )
    endings = data.get("endings")
    if not isinstance(endings, dict):
        raise TypeError(
            f"endings.yaml must contain an 'endings' mapping, "
            f"got {type(endings).__name__}"
        )
    return endings
