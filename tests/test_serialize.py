"""Tests for T27: JSON serialize + atomic save + backup-on-write.

Locks the contract:
- ``serialize(state)`` returns the v1 envelope ``{"version": 1, "state": {...},
  "saved_at_iso": "..."}``.
- Enum values are encoded via ``.value`` (NOT ``str(enum_member)`` which yields
  ``"DepartmentType.MARKETING"``).
- ``save(state, path)`` writes the JSON atomically (write to ``.tmp`` then
  ``os.replace``) and creates a ``.bak`` copy of the previous file on the
  second and later saves.
- ``new_game(42)`` round-trips: serialize -> reconstruct -> ``state_hash``
  matches the original.

T28 will add the symmetric ``deserialize``; for T27 we reconstruct by hand.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path

import pytest

from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.state import (
    Company,
    GameState,
    GameTime,
    new_game,
    state_hash,
)
from htop_tycoon.persistence.serialize import save, serialize

# ---------------------------------------------------------------------------
# serialize() — envelope shape
# ---------------------------------------------------------------------------


def test_serialize_returns_envelope_dict() -> None:
    """serialize must return a dict with exactly {version, state, saved_at_iso}."""
    payload = serialize(new_game(42))
    assert isinstance(payload, dict)
    assert set(payload.keys()) == {"version", "state", "saved_at_iso"}


def test_serialize_version_is_one() -> None:
    """Schema version is locked at 1 for v0.1.0 (per T28's migration contract)."""
    payload = serialize(new_game(42))
    assert payload["version"] == 1


def test_serialize_saved_at_iso_is_parseable_iso() -> None:
    """saved_at_iso must round-trip through ``datetime.fromisoformat``."""
    payload = serialize(new_game(42))
    iso = payload["saved_at_iso"]
    assert isinstance(iso, str)
    parsed = datetime.fromisoformat(iso)
    assert isinstance(parsed, datetime)


def test_serialize_state_subdict_has_all_gamestate_fields() -> None:
    """The state sub-dict must mirror GameState's field names (forward-compat)."""
    state = new_game(42)
    expected = {
        "company",
        "departments",
        "employees",
        "products",
        "competitors",
        "events_active",
        "ending_history",
        "secret_investor_cleared",
        "tick",
        "rng_seed",
        "game_time",
        "version",
    }
    payload = serialize(state)
    assert set(payload["state"].keys()) == expected


def test_serialize_company_subdict_matches_asdict() -> None:
    """The company sub-dict is the asdict() form of the Company aggregate."""
    state = new_game(42)
    payload = serialize(state)
    assert payload["state"]["company"] == dataclasses.asdict(state.company)


def test_serialize_game_time_subdict_has_year_quarter_week() -> None:
    """The game_time sub-dict must contain the locked (year, quarter, week) triple."""
    state = new_game(42)
    payload = serialize(state)
    gt = payload["state"]["game_time"]
    assert gt == {"year": 1, "quarter": 1, "week": 1}


def test_serialize_empty_collections_remain_empty() -> None:
    """new_game() returns empty dicts/lists; serialize must preserve emptiness."""
    payload = serialize(new_game(42))
    s = payload["state"]
    assert s["departments"] == {}
    assert s["employees"] == {}
    assert s["products"] == {}
    assert s["competitors"] == {}
    assert s["events_active"] == []
    assert s["ending_history"] == []


def test_serialize_preserves_scalar_fields() -> None:
    """tick, rng_seed, secret_investor_cleared, version pass through unchanged."""
    state = new_game(42)
    payload = serialize(state)
    s = payload["state"]
    assert s["tick"] == 0
    assert s["rng_seed"] == 42
    assert s["secret_investor_cleared"] is False
    assert s["version"] == 1


# ---------------------------------------------------------------------------
# serialize() — custom encoder (Enum, datetime)
# ---------------------------------------------------------------------------


def test_serialize_enum_uses_value_not_repr() -> None:
    """Enum members inside the state tree serialize as ``.value``, not str repr.

    ``str(DepartmentType.MARKETING)`` is ``"DepartmentType.MARKETING"``; that
    leaks the class name into the JSON. The contract is ``.value`` only.
    """
    dept = Department(
        id="dept-mkt",
        type=DepartmentType.Marketing,
        head_employee_id=None,
        employee_ids=[],
        founded_tick=0,
        unlocked=True,
    )
    state_with_dept = dataclasses.replace(
        new_game(42), departments={"dept-mkt": dept}
    )
    payload = serialize(state_with_dept)
    serialized_type = payload["state"]["departments"]["dept-mkt"]["type"]
    assert serialized_type == DepartmentType.Marketing.value
    assert serialized_type == "Marketing"
    assert "DepartmentType" not in serialized_type


def test_serialize_json_round_trip_is_legal_json() -> None:
    """The serialize output must be JSON-encodable (json.dumps on it must not raise)."""
    payload = serialize(new_game(42))
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    assert decoded["version"] == 1
    assert decoded["state"]["rng_seed"] == 42


# ---------------------------------------------------------------------------
# serialize() — round-trip via manual reconstruction
# ---------------------------------------------------------------------------


def _reconstruct_state(payload: dict) -> GameState:
    """Reconstruct a GameState from a serialize() payload (T28's job, hand-rolled here)."""
    s = payload["state"]
    return GameState(
        company=Company(**s["company"]),
        departments=s["departments"],
        employees=s["employees"],
        products=s["products"],
        competitors=s["competitors"],
        events_active=s["events_active"],
        ending_history=s["ending_history"],
        secret_investor_cleared=s["secret_investor_cleared"],
        tick=s["tick"],
        rng_seed=s["rng_seed"],
        game_time=GameTime(**s["game_time"]),
        version=s["version"],
    )


def test_serialize_round_trip_state_hash_matches_for_new_game() -> None:
    """serialize(new_game(42)) -> reconstruct -> state_hash equals original hash."""
    original = new_game(42)
    payload = serialize(original)
    reconstructed = _reconstruct_state(payload)
    assert state_hash(reconstructed) == state_hash(original)


def test_serialize_round_trip_state_hash_matches_after_replace() -> None:
    """A modified state must round-trip too (tick changed)."""
    original = new_game(42)
    advanced = dataclasses.replace(original, tick=7)
    payload = serialize(advanced)
    reconstructed = _reconstruct_state(payload)
    assert state_hash(reconstructed) == state_hash(advanced)
    assert reconstructed.tick == 7


# ---------------------------------------------------------------------------
# save() — atomic write + backup-on-write
# ---------------------------------------------------------------------------


def test_save_writes_json_file_at_path(tmp_path: Path) -> None:
    """save() writes a JSON file at the given path with the envelope shape."""
    save_path = tmp_path / "save.json"
    save(new_game(42), save_path)
    assert save_path.exists()
    parsed = json.loads(save_path.read_text(encoding="utf-8"))
    assert parsed["version"] == 1
    assert "state" in parsed
    assert "saved_at_iso" in parsed


def test_save_does_not_create_backup_on_first_save(tmp_path: Path) -> None:
    """First save: no previous file exists, so no backup is created."""
    save_path = tmp_path / "save.json"
    backup_path = save_path.with_suffix(".bak")
    save(new_game(42), save_path)
    assert save_path.exists()
    assert not backup_path.exists()


def test_save_creates_backup_on_second_save(tmp_path: Path) -> None:
    """Second save: previous file is copied to ``path.with_suffix('.bak')``."""
    save_path = tmp_path / "save.json"
    backup_path = save_path.with_suffix(".bak")
    state_a = new_game(42)
    state_b = dataclasses.replace(state_a, tick=5)
    save(state_a, save_path)
    save(state_b, save_path)
    assert backup_path.exists()


def test_save_backup_contains_first_state_not_second(tmp_path: Path) -> None:
    """The backup must snapshot the PREVIOUS state, not the new one."""
    save_path = tmp_path / "save.json"
    backup_path = save_path.with_suffix(".bak")
    state_a = new_game(42)
    state_b = dataclasses.replace(state_a, tick=5)
    save(state_a, save_path)
    save(state_b, save_path)

    backup_data = json.loads(backup_path.read_text(encoding="utf-8"))
    assert backup_data["state"]["tick"] == 0
    assert backup_data["state"]["rng_seed"] == 42


def test_save_main_file_reflects_latest_state(tmp_path: Path) -> None:
    """The main file is always the latest saved state."""
    save_path = tmp_path / "save.json"
    state_a = new_game(42)
    state_b = dataclasses.replace(state_a, tick=99)
    save(state_a, save_path)
    save(state_b, save_path)
    main_data = json.loads(save_path.read_text(encoding="utf-8"))
    assert main_data["state"]["tick"] == 99


def test_save_atomic_no_tmp_file_remains(tmp_path: Path) -> None:
    """After a successful save, no ``.tmp`` sibling exists at the path stem."""
    save_path = tmp_path / "save.json"
    tmp_path_str = save_path.with_suffix(".tmp")
    save(new_game(42), save_path)
    assert save_path.exists()
    assert not tmp_path_str.exists()


def test_save_does_not_touch_unrelated_files(tmp_path: Path) -> None:
    """save() only manages ``path`` and ``path.bak``; other files in dir are untouched."""
    save_path = tmp_path / "save.json"
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("do not touch", encoding="utf-8")
    save(new_game(42), save_path)
    assert unrelated.exists()
    assert unrelated.read_text(encoding="utf-8") == "do not touch"


def test_save_atomic_writes_via_tmp_then_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If ``os.replace`` raises mid-save, the main file keeps its previous good content.

    This is the property the spec requires: a crash mid-save must not corrupt
    the previously-saved state. The main file is updated only by ``os.replace``
    which is atomic on POSIX.
    """
    import htop_tycoon.persistence.serialize as serialize_mod

    save_path = tmp_path / "save.json"
    state_a = new_game(42)
    state_b = dataclasses.replace(state_a, tick=99)

    # First save goes through normally.
    save(state_a, save_path)
    main_after_first = save_path.read_text(encoding="utf-8")

    # Patch ``os.replace`` to simulate a crash during the second save.
    def crash_replace(src: str, dst: str) -> None:  # noqa: ARG001
        raise OSError("simulated crash")

    monkeypatch.setattr(serialize_mod.os, "replace", crash_replace)
    with pytest.raises(OSError, match="simulated crash"):
        save(state_b, save_path)

    # Main file is unchanged (still state_a) — atomic replace protected it.
    assert save_path.read_text(encoding="utf-8") == main_after_first
    # The previous tick is still 0.
    assert json.loads(save_path.read_text(encoding="utf-8"))["state"]["tick"] == 0
