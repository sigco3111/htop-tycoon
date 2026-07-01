"""htop-tycoon v3.0 — atomic disk I/O + corruption recovery. Spec §6.

Wave 5 persistence layer:

- :func:`atomic_write` — write to ``.tmp``, ``os.fsync``, then ``os.replace``.
  Survives partial writes (kill -9 mid-write) because the target is only
  replaced atomically after fsync.
- :func:`backup_rotation` — keep last N saves as ``save.bak.1`` ... ``save.bak.N``.
- :func:`load_save_with_recovery` — try main, then backups, then
  ``CORRUPTION_RECOVERY_SEED=0`` fresh ``GameState``.

Spec §6: "Save JSON parse failure: try backup; if both fail,
``CORRUPTION_RECOVERY_SEED=0`` new game + user notification."
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from htop_tycoon.domain import GameState
from htop_tycoon.engine.rng import CORRUPTION_RECOVERY_SEED
from htop_tycoon.persistence.serialize import deserialize_state, serialize_state

# Spec §5.3 / §6 — backup rotation count. Mirrors balance.yaml::save.backup_count.
DEFAULT_BACKUP_COUNT: int = 3


def atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically (spec §6 + AGENTS.md §5).

    Procedure:
      1. Write to ``{path}.tmp`` with a fresh fsync.
      2. ``os.replace(path.tmp, path)`` (POSIX-atomic; on Windows uses
         ReplaceFileW with appropriate flags).

    A crash between (1) and (2) leaves the original ``path`` intact and
    the partial ``.tmp`` orphaned (next save overwrites it).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def backup_rotation(path: Path, count: int = DEFAULT_BACKUP_COUNT) -> None:
    """Rotate ``path`` -> ``path.bak.1`` -> ``path.bak.2`` ... ``path.bak.N``.

    Called immediately after :func:`atomic_write`. Discards the oldest
    backup (``path.bak.N``) so the chain stays bounded.
    """
    path = Path(path)
    if not path.exists():
        return
    for n in range(count - 1, 0, -1):
        src = path.with_suffix(path.suffix + f".bak.{n}")
        dst = path.with_suffix(path.suffix + f".bak.{n + 1}")
        if src.exists():
            shutil.copyfile(src, dst)
    shutil.copyfile(path, path.with_suffix(path.suffix + ".bak.1"))


def save_state(path: Path, state: GameState, *, backup: bool = True) -> None:
    """Atomic save with optional backup rotation (spec §6).

    Order: write FIRST, then rotate. If atomic_write fails the original
    is intact; if backup_rotation fails after a successful write the new
    content is still safe. Rotating AFTER writing also ensures the first
    save creates ``.bak.1`` (with the just-written content); the previous
    order (rotate-then-write) skipped backup creation on the first save
    because ``path`` didn't exist yet.
    """
    atomic_write(path, serialize_state(state))
    if backup:
        backup_rotation(path)


def load_save_with_recovery(
    path: Path,
    *,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> tuple[GameState, str]:
    """Load a save, falling back to backups, then to corruption recovery.

    Returns ``(state, source)`` where ``source`` is one of:
      - ``"main"`` — main save loaded
      - ``"backup.N"`` — Nth backup loaded
      - ``"recovery"`` — both main and backups failed; new game from
        :data:`CORRUPTION_RECOVERY_SEED` (spec §6 "if both fail, ... new game + user notification")

    The recovery state is NOT auto-saved; the caller (UI) is responsible
    for showing a "save corrupted, started new game" notification.
    """
    path = Path(path)
    if path.exists():
        try:
            return deserialize_state(path.read_text(encoding="utf-8")), "main"
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            pass  # fall through to backups

    # Try backups in reverse order (newest first).
    for n in range(1, backup_count + 1):
        bak = path.with_suffix(path.suffix + f".bak.{n}")
        if bak.exists():
            try:
                return deserialize_state(bak.read_text(encoding="utf-8")), f"backup.{n}"
            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                continue

    # Spec §6: corruption recovery — fresh game from
    # CORRUPTION_RECOVERY_SEED (defined in engine.rng; spec §5.3 forbids
    # deriving it from time.time()).
    recovery = GameState(rng_seed=CORRUPTION_RECOVERY_SEED)
    return recovery, "recovery"


__all__ = [
    "DEFAULT_BACKUP_COUNT",
    "atomic_write",
    "backup_rotation",
    "load_save_with_recovery",
    "save_state",
]
