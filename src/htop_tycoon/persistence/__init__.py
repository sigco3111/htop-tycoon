"""htop-tycoon v3.0 — Persistence layer (Wave 5). Spec §5.3 + §6.

Public API:

  Save / load:
    - save_state(path, state)         — atomic write with backup rotation
    - load_save_with_recovery(path)   — main + backups + recovery fallback
    - atomic_write(path, content)     — write to .tmp, fsync, os.replace
    - backup_rotation(path, count=3)  — keep last N saves

  Serialization (canonical):
    - serialize_state(state)  -> str (JSON)
    - deserialize_state(s)     -> GameState
    - SCHEMA_VERSION: int (currently 1)

  Migration:
    - register_migration(from_v, to_v) — decorator for version bumps
    - upgrade_save(payload)             — walk the chain to SCHEMA_VERSION

Spec §6 contract:
  - Save JSON parse failure: try backup; if both fail,
    CORRUPTION_RECOVERY_SEED=0 new game + user notification
    (implemented in load_save_with_recovery's "recovery" branch).
  - Save SCHEMA_VERSION mismatch: persistence.migration.upgrade_vN_to_vN+1
    chain (the migration module is the v2+ path; v1 has no chain yet).
"""
from htop_tycoon.persistence.migration import register_migration, upgrade_save
from htop_tycoon.persistence.serialize import (
    SCHEMA_VERSION,
    deserialize_state,
    serialize_state,
)
from htop_tycoon.persistence.storage import (
    DEFAULT_BACKUP_COUNT,
    atomic_write,
    backup_rotation,
    load_save_with_recovery,
    save_state,
)

__all__ = [
    "DEFAULT_BACKUP_COUNT",
    "SCHEMA_VERSION",
    "atomic_write",
    "backup_rotation",
    "deserialize_state",
    "load_save_with_recovery",
    "register_migration",
    "save_state",
    "serialize_state",
    "upgrade_save",
]
