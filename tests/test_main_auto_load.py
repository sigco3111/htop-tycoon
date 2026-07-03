"""v3.1.2: main()이 저장된 게임 데이터가 있으면 자동 로드."""

from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

from htop_tycoon.domain import CompanyState
from htop_tycoon.persistence import save_state
from htop_tycoon.ui.mock_state import mock_state


def _build_parser():
    from htop_tycoon.__main__ import _build_parser
    return _build_parser()


def _build_initial_state(args, save_path: Path) -> CompanyState:
    from htop_tycoon.__main__ import _build_initial_state
    return _build_initial_state(args, save_path)


def _persist(state: CompanyState, path: Path) -> None:
    save_state(state, path)


def _args_with_speed(speed: int) -> argparse.Namespace:
    return argparse.Namespace(speed=speed)


def test_build_state_uses_mock_when_no_save_file(tmp_path: Path) -> None:
    """저장 파일이 없으면 mock_state로 시작."""
    save_path = tmp_path / "save.yaml"
    assert not save_path.exists()

    args = _args_with_speed(speed=0)
    state = _build_initial_state(args, save_path)

    assert state.employees, "mock_state should have employees"
    assert state.cash.cents == 100_000_00, "mock_state default cash"
    assert state.auto_on is True, "auto mode enabled by default"


def test_build_state_loads_from_save_file(tmp_path: Path) -> None:
    """저장 파일이 있으면 로드 (cash 변경 등 반영)."""
    save_path = tmp_path / "save.yaml"
    saved_state = mock_state(speed=0)
    saved_state = dataclasses.replace(saved_state, cash=type(saved_state.cash)(42_000_00))
    _persist(saved_state, save_path)
    assert save_path.exists()

    args = _args_with_speed(speed=0)
    loaded = _build_initial_state(args, save_path)

    assert loaded.cash.cents == 42_000_00, "should load saved cash"
    assert loaded.auto_on is True, "auto mode enabled after load"


def test_build_state_recovers_from_corrupt_save_file(tmp_path: Path) -> None:
    """손상된 저장 파일은 무시하고 mock_state로 fallback."""
    save_path = tmp_path / "save.yaml"
    save_path.write_text("not a valid yaml: : :", encoding="utf-8")

    args = _args_with_speed(speed=0)
    state = _build_initial_state(args, save_path)

    assert state.employees, "should fallback to mock_state"
    assert state.auto_on is True


def test_load_preserves_restore_cash_value(tmp_path: Path) -> None:
    """load_state가 round-trip으로 cash 값 보존."""
    from htop_tycoon.persistence import load_state

    save_path = tmp_path / "save.yaml"
    saved = mock_state(speed=0)
    saved = dataclasses.replace(saved, cash=type(saved.cash)(777_77))
    _persist(saved, save_path)

    loaded = load_state(save_path)
    assert loaded.cash.cents == 777_77