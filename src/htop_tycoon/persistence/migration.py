"""htop-tycoon v3.0 — schema migration stub. Spec §6.

Spec §6: "Save SCHEMA_VERSION mismatch: ``persistence.migration
.upgrade_vN_to_vN+1`` chain."

The current schema version is 1 (see :data:`SCHEMA_VERSION` in
:mod:`persistence.serialize`). When the format changes, add an
``upgrade_vN_to_vN_plus_1`` function and bump ``SCHEMA_VERSION``. The
chain must be transitive: every save file can reach the latest version
via sequential upgrades.
"""
from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from htop_tycoon.persistence.serialize import SCHEMA_VERSION

# Type alias for migration functions: take the dict representation of
# the save, mutate in place (or return a new dict), return the same.
Migration = Callable[[dict[str, Any]], dict[str, Any]]


# Registry of migrations. Populate as new schema versions ship.
_MIGRATIONS: dict[int, Migration] = {}


def register_migration(from_version: int, to_version: int) -> Callable[[Migration], Migration]:
    """Decorator: register ``func`` as the v{from} -> v{to} migration."""
    if to_version != from_version + 1:
        raise ValueError(
            f"migrations must be sequential: v{from_version} -> v{to_version} "
            f"is not v{from_version} -> v{from_version + 1}"
        )
    if from_version in _MIGRATIONS:
        raise ValueError(f"migration already registered for v{from_version}")

    def decorator(func: Migration) -> Migration:
        _MIGRATIONS[from_version] = func
        return func

    return decorator


def upgrade_save(payload: dict[str, Any]) -> dict[str, Any]:
    """Walk the migration chain until ``payload['schema_version']`` matches
    :data:`SCHEMA_VERSION`. No-op when the save is already current.
    """
    current = int(payload["schema_version"])
    payload = copy.deepcopy(payload)
    while current < SCHEMA_VERSION:
        migrator = _MIGRATIONS.get(current)
        if migrator is None:
            raise ValueError(
                f"no migration registered from schema_version={current} "
                f"to {current + 1}; cannot upgrade to {SCHEMA_VERSION}"
            )
        payload = migrator(payload)
        current = int(payload["schema_version"])
    return payload


__all__ = ["register_migration", "upgrade_save"]
