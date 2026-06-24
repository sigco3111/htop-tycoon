"""Korean name generator for the hire system (T10a).

Loads first/last name pools from ``src/htop_tycoon/data/korean_names.yaml`` and
produces deterministic full names via the project's ``GameRNG``.

Contract:
    generate_korean_name(rng) -> str
        Returns ``last_name + first_name`` (no separator) using ``rng.choice``
        over each pool. Same RNG seed yields the same name; the function is a
        pure pass-through into the deterministic RNG and never touches wall
        clock or hardcoded lists.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from htop_tycoon.engine.rng import GameRNG


@lru_cache(maxsize=1)
def _load_name_pool() -> tuple[list[str], list[str]]:
    """Load the (first_names, last_names) tuple from the YAML data file.

    The result is cached for the process lifetime because the pool is static
    and re-reading the YAML on every call would be wasteful and non-deterministic
    with respect to filesystem timing.
    """
    yaml_path = Path(__file__).resolve().parent.parent / "data" / "korean_names.yaml"
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    first_names: list[str] = list(raw["first_names"])
    last_names: list[str] = list(raw["last_names"])
    return first_names, last_names


def generate_korean_name(rng: GameRNG) -> str:
    """Return a deterministic Korean full name ``last_name + first_name``.

    Args:
        rng: A ``GameRNG`` instance. The same instance state yields the same
            output; a fresh RNG with the same seed also yields the same output.

    Returns:
        The concatenated last name + first name, both drawn from the loaded
        Korean name pool.

    Raises:
        ValueError: If the loaded pool is missing entries on either side
            (defensive check; the bundled YAML always supplies >=50 / >=30).
    """
    first_names, last_names = _load_name_pool()
    if not first_names:
        raise ValueError("first_names pool is empty; cannot generate name")
    if not last_names:
        raise ValueError("last_names pool is empty; cannot generate name")
    last: str = rng.choice(last_names)
    first: str = rng.choice(first_names)
    return last + first
