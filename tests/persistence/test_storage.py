"""T4 RED: storage primitives — atomic_write, rotate_backups, save_state, load_state."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from htop_tycoon.domain import CompanyState
from htop_tycoon.persistence.storage import (
    atomic_write,
    load_state,
    rotate_backups,
    save_state,
)
from htop_tycoon.ui.mock_state import mock_state


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "out.yaml"
    atomic_write(path, "hello: world\n")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "hello: world\n"


def test_atomic_write_no_leftover_tmp(tmp_path: Path) -> None:
    path = tmp_path / "out.yaml"
    atomic_write(path, "x: 1\n")
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == [], f"Leftover .tmp files: {leftovers}"


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    path = tmp_path / "out.yaml"
    atomic_write(path, "first\n")
    atomic_write(path, "second\n")
    assert path.read_text(encoding="utf-8") == "second\n"


def test_rotate_backups_no_existing_is_noop(tmp_path: Path) -> None:
    rotate_backups(tmp_path, "save", keep=3)
    files = list(tmp_path.glob("save*"))
    assert files == []


def test_rotate_backups_keeps_n_plus_1(tmp_path: Path) -> None:
    """After save+rotate, total save files == keep (live + backups)."""
    base = tmp_path / "save.yaml"
    for i in range(5):
        state = CompanyState(day_index=i)
        save_state(state, base)
    files = sorted(tmp_path.glob("save*.yaml"))
    assert len(files) == 3
    assert base.exists()


def test_rotate_backups_shifts_index(tmp_path: Path) -> None:
    """After multiple saves, .1.yaml should be newer than .2.yaml."""
    base = tmp_path / "save.yaml"
    for i in range(3):
        save_state(CompanyState(day_index=i), base)
    assert base.exists()
    assert (tmp_path / "save.1.yaml").exists()
    assert (tmp_path / "save.2.yaml").exists()


def test_save_state_creates_yaml(tmp_path: Path) -> None:
    state = mock_state(speed=1)
    save_state(state, tmp_path / "save.yaml")
    text = (tmp_path / "save.yaml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    assert parsed["version"] == 2
    assert parsed["state"]["year"] == 1


def test_load_state_roundtrip(tmp_path: Path) -> None:
    state = mock_state(speed=1)
    path = tmp_path / "save.yaml"
    save_state(state, path)
    restored = load_state(path)
    assert restored == state


def test_load_state_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_state(tmp_path / "missing.yaml")


def test_load_state_corrupt_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("not: valid: yaml: at all\n  : :: ::", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        load_state(path)
