"""htop-tycoon v3.0 — GameState JSON serialization (spec §5.3, §6).

Two-way conversion between ``GameState`` and a JSON string. The canonical
serialization matches the layout used by :func:`compute_game_state_hash`
(spec §7.3) so a save file's SHA-256 is identical to ``state.compute_hash()``
without re-hashing the file. This is what lets the frozen-hash regression
test verify that a load + save roundtrip is bit-identical.
"""
from __future__ import annotations

import dataclasses
import json
from types import MappingProxyType
from typing import Any

from htop_tycoon.domain import (
    Employee,
    GameState,
    QualityAxis,
)

SCHEMA_VERSION: int = 1  # bumped whenever the on-disk format changes


def _to_canonical(obj: Any) -> Any:
    """Recursively convert ``GameState`` (and nested types) to a JSON-safe form.

    Mirrors the canonical form used by :func:`compute_game_state_hash` so a
    roundtrip through ``serialize_state`` -> ``deserialize_state`` reproduces
    the same ``compute_hash()`` output. MappingProxyType wrappers are
    unwrapped to dict (frozen dataclasses to dict, etc.).
    """
    import dataclasses
    from collections.abc import Mapping
    from types import MappingProxyType

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_canonical(getattr(obj, f.name))
                for f in dataclasses.fields(obj)}
    if isinstance(obj, (MappingProxyType, Mapping)):
        return {k: _to_canonical(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return [_to_canonical(v) for v in obj]
    return obj


def serialize_state(state: GameState) -> str:
    """Serialize ``state`` to a JSON string (spec §5.3 + §6).

    Output is ``{schema_version, rng_seed, state}`` where ``state`` is the
    canonical GameState representation. ``compute_hash(state)`` and
    re-parsing this string + applying ``compute_hash`` again must agree.
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "rng_seed": state.rng_seed,
        "state": _to_canonical(state),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deserialize_state(payload: str) -> GameState:
    """Inverse of :func:`serialize_state` (spec §5.3 + §6).

    Schema-version aware: the current implementation accepts version 1 and
    rejects others (frozen-hash regression catches drift). The migration
    layer (``persistence.migration``) is the only path for version bumps.
    """
    data = json.loads(payload)
    version = int(data["schema_version"])
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema_version={version}; expected {SCHEMA_VERSION}. "
            f"Run persistence.migration.upgrade_v{version}_to_v{SCHEMA_VERSION} first."
        )
    return _state_from_dict(data["state"])


def _build_employee(e: dict[str, Any]) -> Employee:
    """Reconstruct an ``Employee`` from its canonical dict form.

    Employee has two ``init=False`` fields (``salary_daily`` and
    ``skill_per_axis``) computed in ``__post_init__`` from ``(job, level)``.
    The serialized form carries both fields explicitly so we use
    ``dataclasses.replace`` to override the computed values with the
    deserialized ones (this preserves the roundtrip invariant under
    ``compute_hash``).
    """
    emp = Employee(
        id=e["id"],
        name=e["name"],
        dept=e["dept"],
        job=e["job"],
        level=e["level"],
        satisfaction=e.get("satisfaction", 0.6),
        joined_day=e.get("joined_day", 1),
    )
    skill_dict = {
        _quality_axis_from_str(k): float(v)
        for k, v in e.get("skill_per_axis", {}).items()
    }
    return dataclasses.replace(
        emp,
        skill_per_axis=MappingProxyType(skill_dict),
    )


def _quality_axis_from_str(s: str) -> QualityAxis:
    """Reconstruct a QualityAxis from its serialized string form.

    JSON serializes IntEnum keys as their integer value (e.g., "1"), but a
    future schema bump or name-based encoding could emit names like "FUN".
    This helper accepts both forms.
    """
    if s in QualityAxis.__members__:
        return QualityAxis[s]  # by name (e.g., "FUN")
    return QualityAxis(int(s))  # by value (e.g., "1")


def _state_from_dict(d: dict[str, Any]) -> GameState:
    """Reconstruct a ``GameState`` from its canonical dict form.

    Domain re-import inside the function to avoid circular import at module
    load time (this module is imported during engine init, before the
    domain is fully re-exported).
    """
    from htop_tycoon.domain import (
        Ending,
        Event,
        GameProject,
        GameState,
        LegacyScore,
        Market,
    )

    employees: tuple[Employee, ...] = tuple(
        _build_employee(e) for e in d["employees"]
    )
    projects_list: list[dict[str, Any]] = d["projects"]
    projects: tuple[GameProject, ...] = tuple(
        GameProject(
            id=p["id"],
            name=p["name"],
            genre_id=p["genre_id"],
            theme_id=p["theme_id"],
            platform_id=p["platform_id"],
            progress_pct=p["progress_pct"],
            # quality_axes: JSON has string keys (enum members serialized via
            # str()); reconstruct as QualityAxis enum members for equality.
            quality_axes={
                _quality_axis_from_str(k): float(v)
                for k, v in p["quality_axes"].items()
            },
            assignees=tuple(p.get("assignees", ())),
            started_day=p["started_day"],
            sales_total=p["sales_total"],
            fan_boost=p["fan_boost"],
            released_day=p.get("released_day"),
        )
        for p in projects_list
    )
    market_data = d["market"]
    market = Market(
        consoles=tuple(market_data.get("consoles", ())),
        last_decay_day=market_data["last_decay_day"],
    )
    legacy = LegacyScore(
        achievements=tuple(d["legacy"].get("achievements", ())),
        points=d["legacy"].get("points", 0),
    )
    ending = Ending(**d["ending"]) if d.get("ending") is not None else None
    events: tuple[Event, ...] = tuple(Event(**e) for e in d.get("events", ()))

    return GameState(
        day=d["day"],
        cash=d["cash"],
        fans=d["fans"],
        employees=employees,
        projects=projects,
        market=market,
        legacy=legacy,
        ending=ending,
        rng_seed=d["rng_seed"],
        events=events,
    )


__all__ = ["SCHEMA_VERSION", "serialize_state", "deserialize_state"]
