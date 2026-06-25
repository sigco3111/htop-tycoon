"""T27: JSON serialize + atomic save + backup-on-write.

This module is the *write* half of the persistence layer. The *read* half
(``deserialize`` + corruption recovery) lives in T28.

Two public functions:

- :func:`serialize` — convert a frozen :class:`~htop_tycoon.domain.state.GameState`
  to the v1 JSON envelope ``{"version": 1, "state": {...}, "saved_at_iso": "..."}``.
  The returned ``dict`` is fully JSON-native (Enums pre-encoded via
  ``.value``, datetimes pre-encoded via ISO-8601); ``json.dumps(payload)``
  works without a ``default=`` hook.
- :func:`save` — atomically write the envelope to ``path`` (write to
  ``path.with_suffix('.tmp')`` then ``os.replace``) and snapshot the
  previous file (if any) to ``path.with_suffix('.bak')``.

The atomic-replace guarantee: a crash mid-save leaves the previous good
state intact at ``path``. ``os.replace`` is atomic on POSIX and Windows.
The ``.tmp`` file may remain on disk as debris after a crash; it is
removed by the next successful save (``os.replace`` does not delete
source on Windows, but it does on POSIX; either way, the next save
re-creates it cleanly).
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from htop_tycoon.domain.state import GameState

__all__ = ["SCHEMA_VERSION", "save", "serialize"]

# Locked at 1 for v0.1.0. T28's corruption recovery uses this constant to
# decide whether a payload is loadable as-is or needs migration.
SCHEMA_VERSION: int = 1


def _json_default(obj: Any) -> Any:
    """Fallback encoder for special types not handled by ``json.dumps`` natively.

    The :func:`serialize` entry point pre-encodes the state tree so the
    public envelope is plain JSON; this hook is kept as a safety net for
    callers who hand the raw ``dataclasses.asdict(state)`` (with live
    Enum/datetime values) to ``json.dumps``.

    - ``Enum``: emit ``.value`` (NOT ``str(member)`` — that would leak
      the class name, e.g. ``"DepartmentType.Marketing"``).
    - ``datetime``: emit ISO-8601 via ``.isoformat()`` (timezone-aware).
    - everything else: fall through to ``str(obj)`` for parity with the
      canonical hash format used by ``state_hash``.
    """
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def serialize(state: GameState) -> dict[str, Any]:
    """Convert a frozen :class:`GameState` to the v1 JSON envelope.

    Returns a plain ``dict`` (NOT a JSON string) with three keys:

    - ``"version"``: always ``SCHEMA_VERSION`` (1 for v0.1.0).
    - ``"state"``: nested dict tree produced by ``dataclasses.asdict(state)``
      with all Enum/datetime values pre-encoded (so the dict is JSON-native
      and ``json.dumps`` works without ``default=``).
    - ``"saved_at_iso"``: ISO-8601 UTC timestamp captured at call time.
      This field is metadata, NOT part of the canonical state hash.
    """
    # Round-trip through json to convert Enum/datetime to plain types.
    state_dict: dict[str, Any] = json.loads(
        json.dumps(dataclasses.asdict(state), default=_json_default)
    )
    return {
        "version": SCHEMA_VERSION,
        "state": state_dict,
        "saved_at_iso": datetime.now(UTC).isoformat(),
    }


def save(state: GameState, path: Path) -> None:
    """Atomically write ``state`` to ``path`` and snapshot the previous file.

    Order of operations (chosen for crash safety — backup before mutation):

    1. If ``path`` exists, copy it to ``path.with_suffix('.bak')``. This
       preserves the previously-saved state for T28's corruption recovery.
    2. Write the new envelope to ``path.with_suffix('.tmp')``.
    3. ``os.replace(tmp, path)`` — atomic on POSIX and Windows. Either
       the old file or the new file is visible at ``path``; never partial.

    A crash mid-save leaves the previous good state at ``path``; the
    ``.tmp`` file may exist as debris but the next successful ``save``
    cleans it up via ``os.replace`` (or overwrites it).

    The ``.bak`` file is overwritten on every save after the first.
    """
    backup_path = path.with_suffix(".bak")
    if path.exists():
        shutil.copy2(path, backup_path)

    tmp_path = path.with_suffix(".tmp")
    payload = serialize(state)
    encoded = json.dumps(payload, ensure_ascii=False)
    tmp_path.write_text(encoded, encoding="utf-8")
    os.replace(tmp_path, path)
