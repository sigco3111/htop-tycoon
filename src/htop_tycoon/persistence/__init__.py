"""Persistence layer — Save/Load CompanyState as YAML.

Phase 2F. Public API:
- to_yaml(state) / from_yaml(text): serialize ↔ deserialize
- save_state(state, path) / load_state(path): atomic write + load
- atomic_write / rotate_backups: low-level FS primitives
- SCHEMA_VERSION: current schema version (1)
- PersistenceVersionError: raised on missing/future version
- SAVE_PATH: default save location (~/.local/share/htop-tycoon/save.yaml)
- HTOP_TYCOON_SAVE_DIR: env var to override save directory
"""

from __future__ import annotations

import os
from pathlib import Path

from htop_tycoon.persistence.serialize import (
    SCHEMA_VERSION,
    PersistenceVersionError,
    from_yaml,
    to_yaml,
)
from htop_tycoon.persistence.storage import (
    atomic_write,
    load_state,
    rotate_backups,
    save_state,
)

__all__ = [
    "SCHEMA_VERSION",
    "PersistenceVersionError",
    "to_yaml",
    "from_yaml",
    "atomic_write",
    "rotate_backups",
    "save_state",
    "load_state",
    "SAVE_PATH",
    "htop_tycoon_save_dir",
]


def htop_tycoon_save_dir() -> Path:
    """Resolve save directory: HTOP_TYCOON_SAVE_DIR env > XDG default."""
    env_dir = os.environ.get("HTOP_TYCOON_SAVE_DIR")
    directory = Path(env_dir) if env_dir else Path.home() / ".local" / "share" / "htop-tycoon"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


SAVE_PATH: Path = htop_tycoon_save_dir() / "save.yaml"
