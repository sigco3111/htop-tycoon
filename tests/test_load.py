"""Tests for T28: ``load()`` — file-based deserialization + backup fallback.

Locks the file-IO contract that complements ``test_deserialize.py``:

- ``load(path)`` reads JSON from ``path`` and delegates to ``deserialize``.
- ``json.JSONDecodeError`` on primary -> tries ``path.with_suffix('.bak')``;
  if backup ALSO fails to parse -> recovery state.
- File not found -> recovery state (NO backup try — spec is explicit).
- Backup file with valid JSON but corrupt state sub-dict still recovers
  via ``deserialize``'s corruption path.
"""

from __future__ import annotations

import json
from pathlib import Path

from htop_tycoon.domain.state import new_game, state_hash
from htop_tycoon.persistence.deserialize import load
from htop_tycoon.persistence.serialize import SCHEMA_VERSION, save

# Frozen expected state_hash for the recovery state. Mirrors the constant
# in test_deserialize.py; kept local for self-containment.
RECOVERY_STATE_HASH: str = "0659738b9d8d2105f0b18dec093a4965a697db28a43aff9e36d124cb29b612c4"


# ---------------------------------------------------------------------------
# load() — happy path: round-trip via file
# ---------------------------------------------------------------------------


def test_load_round_trips_saved_state(tmp_path: Path) -> None:
    """save() then load() preserves the state via the on-disk JSON envelope."""
    save_path = tmp_path / "save.json"
    original = new_game(42)
    save(original, save_path)
    loaded = load(save_path)
    assert state_hash(loaded) == state_hash(original)
    assert loaded.rng_seed == 42


# ---------------------------------------------------------------------------
# load() — corruption: garbage JSON
# ---------------------------------------------------------------------------


def test_load_garbage_json_recovers(tmp_path: Path) -> None:
    """A save file with invalid JSON must yield new_game(seed=0)."""
    save_path = tmp_path / "save.json"
    save_path.write_text("this is not valid json {", encoding="utf-8")
    result = load(save_path)
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_load_truncated_json_recovers(tmp_path: Path) -> None:
    """A save file cut off mid-payload must recover."""
    save_path = tmp_path / "save.json"
    save_path.write_text('{"version": 1, "state":', encoding="utf-8")
    result = load(save_path)
    assert state_hash(result) == RECOVERY_STATE_HASH


def test_load_empty_file_recovers(tmp_path: Path) -> None:
    """An empty save file must recover."""
    save_path = tmp_path / "save.json"
    save_path.write_text("", encoding="utf-8")
    result = load(save_path)
    assert state_hash(result) == RECOVERY_STATE_HASH


# ---------------------------------------------------------------------------
# load() — corruption: missing file
# ---------------------------------------------------------------------------


def test_load_missing_file_recovers(tmp_path: Path) -> None:
    """A nonexistent save path must yield new_game(seed=0), not raise."""
    save_path = tmp_path / "does-not-exist.json"
    assert not save_path.exists()
    result = load(save_path)
    assert state_hash(result) == RECOVERY_STATE_HASH


# ---------------------------------------------------------------------------
# load() — corruption: backup file is used when primary is corrupted
# ---------------------------------------------------------------------------


def test_load_uses_backup_when_primary_corrupted(tmp_path: Path) -> None:
    """When primary is garbage JSON but backup is valid, load returns the backup state."""
    save_path = tmp_path / "save.json"
    backup_path = save_path.with_suffix(".bak")

    # Write a valid backup (round-tripped from new_game(123)).
    backup_state = new_game(123)
    save(backup_state, backup_path)
    backup_hash = state_hash(backup_state)

    # Corrupt the primary.
    save_path.write_text("garbage{{{", encoding="utf-8")

    loaded = load(save_path)
    assert state_hash(loaded) == backup_hash
    assert loaded.rng_seed == 123


def test_load_does_not_consult_backup_when_primary_missing(tmp_path: Path) -> None:
    """When primary is missing entirely, load recovers WITHOUT touching backup.

    Per spec: ``FileNotFoundError -> new_game(seed=CORRUPTION_RECOVERY_SEED)``.
    This is correct semantics: a missing primary means the user has no save
    (fresh install or intentional delete). Silently resurrecting a stale
    backup would surprise the user. Backup is only consulted when primary
    exists but is corrupted mid-write.
    """
    save_path = tmp_path / "save.json"
    backup_path = save_path.with_suffix(".bak")

    backup_state = new_game(77)
    save(backup_state, backup_path)

    assert not save_path.exists()

    loaded = load(save_path)
    assert state_hash(loaded) == RECOVERY_STATE_HASH


def test_load_recovers_when_both_primary_and_backup_corrupted(tmp_path: Path) -> None:
    """When BOTH primary and backup are garbage, load still returns new_game(seed=0)."""
    save_path = tmp_path / "save.json"
    backup_path = save_path.with_suffix(".bak")

    save_path.write_text("primary garbage", encoding="utf-8")
    backup_path.write_text("backup garbage", encoding="utf-8")

    loaded = load(save_path)
    assert state_hash(loaded) == RECOVERY_STATE_HASH


def test_load_recovers_when_primary_corrupted_and_backup_missing(tmp_path: Path) -> None:
    """When primary is corrupted and no backup exists, load recovers."""
    save_path = tmp_path / "save.json"
    backup_path = save_path.with_suffix(".bak")

    save_path.write_text("garbage", encoding="utf-8")
    assert not backup_path.exists()

    loaded = load(save_path)
    assert state_hash(loaded) == RECOVERY_STATE_HASH


def test_load_backup_with_bad_state_subdict_recovers(tmp_path: Path) -> None:
    """Backup file that parses but has a malformed state sub-dict still recovers.

    This exercises the full chain: JSONDecodeError -> backup try ->
    deserialize (which sees missing keys) -> recovery.
    """
    save_path = tmp_path / "save.json"
    backup_path = save_path.with_suffix(".bak")

    # Backup is valid JSON but has a truncated state dict.
    backup_path.write_text(
        json.dumps({"version": SCHEMA_VERSION, "state": {"company": {}}}),
        encoding="utf-8",
    )

    # Primary is garbage.
    save_path.write_text("not json", encoding="utf-8")

    loaded = load(save_path)
    assert state_hash(loaded) == RECOVERY_STATE_HASH


def test_load_backup_with_version_999_recovers(tmp_path: Path) -> None:
    """Backup with unknown version -> deserialize recovers to new_game(seed=0)."""
    save_path = tmp_path / "save.json"
    backup_path = save_path.with_suffix(".bak")

    backup_path.write_text(
        json.dumps({"version": 999, "state": {}, "saved_at_iso": "x"}),
        encoding="utf-8",
    )
    save_path.write_text("primary garbage", encoding="utf-8")

    loaded = load(save_path)
    assert state_hash(loaded) == RECOVERY_STATE_HASH
