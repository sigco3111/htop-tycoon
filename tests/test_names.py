"""Tests for T10a: korean_names.yaml pool + generate_korean_name helper.

Contract:
- YAML loads from ``src/htop_tycoon/data/korean_names.yaml``.
- Pool size: >=50 first names, >=30 last names.
- ``generate_korean_name(rng)`` returns ``last + first`` (no separator),
  deterministic for a given RNG instance.
- Empty first_names list OR empty last_names list raises ``ValueError``.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml

# All imports of ``htop_tycoon.engine.*`` go through ``importlib`` (helpers
# below) so tests surface real import errors clearly during parallel work.


NAMES_MODULE = "htop_tycoon.engine.names"
RNG_MODULE = "htop_tycoon.engine.rng"
DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "htop_tycoon"
    / "data"
    / "korean_names.yaml"
)


def _load_names_module() -> object:
    """Late-import names module so tests surface real import errors clearly."""
    return importlib.import_module(NAMES_MODULE)


def _load_rng_class() -> type:
    """Late-import GameRNG (owned by T2) and return its class."""
    return importlib.import_module(RNG_MODULE).GameRNG


# === Pool-shape tests (drive data file content) ===


def test_korean_names_yaml_exists() -> None:
    """Given: korean_names.yaml must ship under src/htop_tycoon/data/.

    When: importing the names module triggers YAML load.
    Then: the YAML file exists on disk.
    """
    assert DATA_PATH.is_file(), f"missing data file: {DATA_PATH}"


def test_korean_names_yaml_parses_with_first_and_last_keys() -> None:
    """Given: korean_names.yaml on disk.

    When: parsed via PyYAML.
    Then: it has ``first_names`` and ``last_names`` keys, each a list of strings.
    """
    raw = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), "YAML root must be a mapping"
    assert "first_names" in raw, "missing first_names key"
    assert "last_names" in raw, "missing last_names key"
    assert isinstance(raw["first_names"], list)
    assert isinstance(raw["last_names"], list)
    assert all(isinstance(n, str) for n in raw["first_names"])
    assert all(isinstance(n, str) for n in raw["last_names"])


def test_first_names_pool_has_at_least_50_entries() -> None:
    """Given: korean_names.yaml loaded.

    When: counting first_names.
    Then: there are at least 50 distinct entries (spec minimum).
    """
    raw = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8"))
    first_names: list[str] = raw["first_names"]
    assert len(first_names) >= 50, f"expected >=50 first names, got {len(first_names)}"
    assert len(set(first_names)) == len(first_names), "first_names must be unique"


def test_last_names_pool_has_at_least_30_entries() -> None:
    """Given: korean_names.yaml loaded.

    When: counting last_names.
    Then: there are at least 30 distinct entries (spec minimum).
    """
    raw = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8"))
    last_names: list[str] = raw["last_names"]
    assert len(last_names) >= 30, f"expected >=30 last names, got {len(last_names)}"
    assert len(set(last_names)) == len(last_names), "last_names must be unique"


def test_names_are_korean_only_hangul() -> None:
    """Given: korean_names.yaml.

    When: scanning every name for non-Hangul code points.
    Then: only Hangul characters appear (no Latin, no Hanja, no emoji).
    """
    raw = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8"))
    for entry in raw["first_names"] + raw["last_names"]:
        for ch in entry:
            code_point = ord(ch)
            is_hangul = (
                0xAC00 <= code_point <= 0xD7A3  # Hangul Syllables
                or 0x1100 <= code_point <= 0x11FF  # Hangul Jamo
                or 0x3130 <= code_point <= 0x318F  # Hangul Compatibility Jamo
            )
            assert is_hangul, f"non-Hangul char {ch!r} (U+{code_point:04X}) in {entry!r}"


# === generate_korean_name behavior tests ===


def test_generate_korean_name_is_deterministic_for_same_seed() -> None:
    """Given: a fresh RNG with seed=42.

    When: generate_korean_name is called twice (same seed each time).
    Then: both calls return the identical full name.
    """
    GameRNG = _load_rng_class()
    generate_korean_name = _load_names_module().generate_korean_name

    first = generate_korean_name(GameRNG(42))
    second = generate_korean_name(GameRNG(42))

    assert first == second
    assert isinstance(first, str)
    assert len(first) >= 2


def test_generate_korean_name_format_is_last_then_first() -> None:
    """Given: a fresh RNG.

    When: generate_korean_name is called.
    Then: the returned string starts with a known last name and continues with
    a known first name from the loaded pools (last name + first name, no gap).
    """
    GameRNG = _load_rng_class()
    generate_korean_name = _load_names_module().generate_korean_name

    raw = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8"))
    last_pool: list[str] = raw["last_names"]
    first_pool: list[str] = raw["first_names"]

    generated = generate_korean_name(GameRNG(7))
    matched_last = next((ln for ln in last_pool if generated.startswith(ln)), None)
    assert matched_last is not None, (
        f"generated name {generated!r} must start with a known last name"
    )
    remainder = generated[len(matched_last):]
    assert remainder in first_pool, (
        f"trailing part {remainder!r} must be a known first name"
    )


def test_generate_korean_name_varies_across_seeds() -> None:
    """Given: 100 RNGs with distinct seeds (0..99).

    When: generate_korean_name is invoked once per RNG.
    Then: at least 10 unique full names appear (the pool has 50+ x 30+ entries
    so collisions must be rare; this is a statistical sanity check, not a
    exhaustive enumeration).
    """
    GameRNG = _load_rng_class()
    generate_korean_name = _load_names_module().generate_korean_name

    names = {generate_korean_name(GameRNG(seed)) for seed in range(100)}
    assert len(names) >= 10, (
        f"expected >=10 unique names over 100 seeds, got {len(names)}: {sorted(names)[:5]}"
    )


def test_generate_korean_name_uses_loaded_pool_not_hardcoded() -> None:
    """Given: a fresh RNG.

    When: generate_korean_name returns a name.
    Then: both the last-name prefix and the first-name suffix come from the
    on-disk YAML pools. This guards against accidental hardcoding of names in
    Python (forbidden by T10a Must-NOT).
    """
    GameRNG = _load_rng_class()
    generate_korean_name = _load_names_module().generate_korean_name

    raw = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8"))
    last_pool = set(raw["last_names"])
    first_pool = set(raw["first_names"])

    generated = generate_korean_name(GameRNG(123))
    matched_last = next((ln for ln in last_pool if generated.startswith(ln)), None)
    assert matched_last is not None
    remainder = generated[len(matched_last):]
    assert remainder in first_pool


# === Failure QA scenarios (from plan line 359) ===


def test_empty_first_names_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given: the loader would return an empty first_names list.

    When: generate_korean_name is called.
    Then: it raises ValueError (plan QA failure scenario).
    """
    names_module = _load_names_module()
    # Bypass lru_cache to inject a controlled empty pool.
    monkeypatch.setattr(
        names_module,
        "_load_name_pool",
        lambda: ([], ["김", "이", "박"]),
    )

    GameRNG = _load_rng_class()
    with pytest.raises(ValueError):
        names_module.generate_korean_name(GameRNG(0))


def test_empty_last_names_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given: the loader would return an empty last_names list.

    When: generate_korean_name is called.
    Then: it raises ValueError (plan QA failure scenario).
    """
    names_module = _load_names_module()
    monkeypatch.setattr(
        names_module,
        "_load_name_pool",
        lambda: (["민준", "서연"], []),
    )

    GameRNG = _load_rng_class()
    with pytest.raises(ValueError):
        names_module.generate_korean_name(GameRNG(0))


# === Caching sanity (lru_cache must keep the same pool across calls) ===


def test_pool_is_cached_across_calls() -> None:
    """Given: multiple generate_korean_name invocations.

    When: comparing the underlying pool object identity.
    Then: the same tuple is reused (lru_cache on _load_name_pool).
    """
    names_module = _load_names_module()
    first_pool = names_module._load_name_pool()
    second_pool = names_module._load_name_pool()
    assert first_pool is second_pool, "_load_name_pool must be cached"
