"""htop-tycoon v3.0 — Pilot scenario 5: save_load_roundtrip (spec §7.4).

Verifies that saving then loading produces an identical GameState
(compute_hash invariant) and that the persistence layer's recovery
fallback works when the save file is corrupted.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from htop_tycoon.domain import (
    Department,
    GameProject,
    GameState,
    GenreId,
    JobType,
    Platform,
    PlatformId,
    ProjectId,
    QualityAxis,
    ThemeId,
)
from htop_tycoon.engine import actions as engine_actions
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.persistence import load_save_with_recovery, save_state
from htop_tycoon.ui import HtopTycoonApp


@pytest.mark.asyncio
async def test_save_load_roundtrip_preserves_compute_hash(tmp_path: Path) -> None:
    """Spec §7.4: 'press S -> save -> restart -> load -> identical state'."""
    state = GameState(cash=42_000, fans=100, rng_seed=42)
    # Save to a temp file
    target = tmp_path / "save.json"
    save_state(target, state)
    # Load it back
    loaded_state, source = load_save_with_recovery(target)
    assert source == "main"
    assert loaded_state.compute_hash() == state.compute_hash()


@pytest.mark.asyncio
async def test_save_load_roundtrip_preserves_employees(tmp_path: Path) -> None:
    """Employees/projects/fans all survive a save+load roundtrip."""
    state = GameState(cash=100_000, rng_seed=42)
    state, _ = engine_actions.hire(
        state, GameRNG(42),
        dept=Department.PLANNING,
        job=JobType.GAME_DESIGNER,
    )
    p = GameProject(
        id=ProjectId("p1"),
        name="Test RPG",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=42.0,
        quality_axes={
            QualityAxis.FUN: 6.0,
            QualityAxis.GRAPHICS: 5.0,
            QualityAxis.SOUND: 4.0,
            QualityAxis.ORIGINALITY: 7.0,
        },
    )
    state = state.replace(projects=(p,))

    target = tmp_path / "save.json"
    save_state(target, state)
    loaded, _ = load_save_with_recovery(target)
    assert loaded.employees == state.employees
    assert loaded.projects == state.projects
    assert loaded.cash == state.cash
    assert loaded.fans == state.fans


@pytest.mark.asyncio
async def test_save_load_corrupted_main_falls_back_to_backup(tmp_path: Path) -> None:
    """Spec §6: 'try backup; if both fail, CORRUPTION_RECOVERY_SEED=0'."""
    state = GameState(cash=10_000, rng_seed=42)
    target = tmp_path / "save.json"
    save_state(target, state)
    # Save again so a backup exists
    save_state(target, state.replace(cash=20_000))
    # Corrupt main
    target.write_text("not valid json", encoding="utf-8")
    # The first call falls back to bak.1
    loaded, source = load_save_with_recovery(target)
    assert source == "backup.1"
    # bak.1 is the NEWEST backup — it's the second save, so cash=20000
    assert loaded.cash == 20_000


@pytest.mark.asyncio
async def test_save_load_all_corrupted_returns_recovery(tmp_path: Path) -> None:
    """Spec §6: when ALL sources fail, return recovery (seed=0 new game)."""
    target = tmp_path / "save.json"
    save_state(target, GameState(cash=1_000))
    # Corrupt everything
    target.write_text("not valid json", encoding="utf-8")
    for n in range(1, 4):
        bak = target.with_suffix(target.suffix + f".bak.{n}")
        if bak.exists():
            bak.write_text("also not valid", encoding="utf-8")
    loaded, source = load_save_with_recovery(target)
    assert source == "recovery"
    # Recovery uses default cash (50000) and seed=0
    from htop_tycoon.engine.rng import CORRUPTION_RECOVERY_SEED
    assert loaded.rng_seed == CORRUPTION_RECOVERY_SEED
    assert loaded.cash == 50_000


@pytest.mark.asyncio
async def test_app_action_save_persists_state(tmp_path: Path) -> None:
    """End-to-end: the app's 'F2' / 'S' binding persists the current state."""
    import os

    from htop_tycoon.persistence import load_save_with_recovery

    # Patch the user's home dir to our tmp dir
    home = tmp_path
    app = HtopTycoonApp(state=GameState(cash=33_000, rng_seed=42), speed=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        # The app's action_save writes to Path.home() / ".htop_tycoon_save.json".
        # Patch HOME for the duration of the test.
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        try:
            app.action_save()
            await pilot.pause()
        finally:
            if old_home is None:
                del os.environ["HOME"]
            else:
                os.environ["HOME"] = old_home
        # Load and verify
        target = home / ".htop_tycoon_save.json"
        assert target.exists()
        loaded, _ = load_save_with_recovery(target)
        assert loaded.cash == 33_000
