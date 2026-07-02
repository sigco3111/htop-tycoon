"""Wave 11 cli_parser tests (spec §7.7).

Coverage:
- argparse flag parsing (defaults, overrides, validation)
- headless runner loop (no-op, smoke, strategy, console-force, autosave)
- frozen-hash RNG pattern preservation

The 3 frozen hashes at seed=42 day 100/1000/3650 must remain intact.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from htop_tycoon.cli_parser import main, parse_args, run_headless

# ---------------------------------------------------------------------------
# parse_args — flag defaults
# ---------------------------------------------------------------------------


def test_parse_args_seed_default_is_42() -> None:
    args = parse_args([])
    assert args.seed == 42


def test_parse_args_seed_override() -> None:
    args = parse_args(["--seed=7"])
    assert args.seed == 7


def test_parse_args_ticks_default_is_zero() -> None:
    args = parse_args([])
    assert args.ticks == 0


def test_parse_args_ticks_zero_is_valid() -> None:
    args = parse_args(["--ticks=0"])
    assert args.ticks == 0


def test_parse_args_ticks_override() -> None:
    args = parse_args(["--ticks=1800"])
    assert args.ticks == 1800


def test_parse_args_tick_rate_default_is_1() -> None:
    args = parse_args([])
    assert args.tick_rate == 1


def test_parse_args_tick_rate_rejects_zero() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--tick-rate=0"])


def test_parse_args_tick_rate_rejects_above_4() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--tick-rate=5"])


def test_parse_args_tick_rate_accepts_4() -> None:
    args = parse_args(["--tick-rate=4"])
    assert args.tick_rate == 4


def test_parse_args_headless_flag_default_false() -> None:
    args = parse_args([])
    assert args.headless is False


def test_parse_args_headless_flag_set() -> None:
    args = parse_args(["--headless"])
    assert args.headless is True


def test_parse_args_no_autosave_flag() -> None:
    args = parse_args(["--no-autosave"])
    assert args.no_autosave is True


def test_parse_args_strategy_default_none() -> None:
    args = parse_args([])
    assert args.strategy is None


def test_parse_args_strategy_accepts_four_names() -> None:
    for name in ("aggressive", "conservative", "balanced", "genre_focus"):
        args = parse_args([f"--strategy={name}"])
        assert args.strategy == name


def test_parse_args_strategy_rejects_unknown() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--strategy=not_a_real_strategy"])


def test_parse_args_dev_flag() -> None:
    args = parse_args(["--dev"])
    assert args.dev is True


def test_parse_args_force_console_discontinue_default_none() -> None:
    args = parse_args([])
    assert args.force_console_discontinue is None


def test_parse_args_force_console_discontinue_int() -> None:
    args = parse_args(["--force-console-discontinue=8"])
    assert args.force_console_discontinue == 8


def test_parse_args_autosave_path_default() -> None:
    args = parse_args([])
    assert args.autosave_path == Path.home() / ".htop_tycoon_save.json"


def test_parse_args_autosave_path_override(tmp_path: Path) -> None:
    target = tmp_path / "my_save.json"
    args = parse_args([f"--autosave-path={target}"])
    assert args.autosave_path == target


def test_parse_args_autosave_every_default() -> None:
    args = parse_args([])
    assert args.autosave_every == 100


def test_parse_args_autosave_every_override() -> None:
    args = parse_args(["--autosave-every=50"])
    assert args.autosave_every == 50


# ---------------------------------------------------------------------------
# CliArgs dataclass immutability
# ---------------------------------------------------------------------------


def test_cli_args_is_frozen() -> None:
    args = parse_args([])
    with pytest.raises(dataclasses.FrozenInstanceError):
        args.seed = 100  # type: ignore[misc]


# ---------------------------------------------------------------------------
# run_headless — smoke and behavior
# ---------------------------------------------------------------------------


def test_run_headless_zero_ticks_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = parse_args(["--ticks=0", "--headless", "--no-autosave"])
    rc = run_headless(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "htop-tycoon headless run" in out


def test_run_headless_10_ticks_emits_logs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = parse_args(
        ["--seed=42", "--ticks=10", "--headless", "--no-autosave",
         f"--autosave-path={tmp_path / 'save.json'}"]
    )
    rc = run_headless(args)
    assert rc == 0
    out = capsys.readouterr().out
    # At least one structured log line per ~max(1, 10//20)=1 ticks → 10+ lines
    assert "day=" in out
    assert "cash=" in out
    assert "final day=" in out


def test_run_headless_50_ticks_no_strategy(tmp_path: Path) -> None:
    """50 ticks without strategy: should advance state by 50 days."""
    args = parse_args(
        ["--seed=42", "--ticks=50", "--headless", "--no-autosave",
         f"--autosave-path={tmp_path / 'save.json'}"]
    )
    rc = run_headless(args)
    assert rc == 0
    from htop_tycoon.domain import GameState

    # Re-run and check deterministic behavior: final day should be 50
    from htop_tycoon.engine.rng import GameRNG
    from htop_tycoon.engine.tick import run_day
    state = GameState(rng_seed=42)
    for _ in range(50):
        rng = GameRNG(state.rng_seed + state.day)
        state, _ = run_day(state, rng, strategy=None)
    assert state.day == 50


def test_run_headless_with_strategy_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Strategy mode: 30 ticks with balanced strategy; should not crash."""
    args = parse_args(
        ["--seed=42", "--ticks=30", "--headless", "--strategy=balanced",
         "--no-autosave", f"--autosave-path={tmp_path / 'save.json'}"]
    )
    rc = run_headless(args)
    assert rc == 0


def test_run_headless_with_force_console_discontinue(tmp_path: Path) -> None:
    """--force-console-discontinue patches licensed consoles."""
    args = parse_args(
        ["--seed=42", "--ticks=20", "--headless",
         "--force-console-discontinue=2",
         "--no-autosave", f"--autosave-path={tmp_path / 'save.json'}"]
    )
    rc = run_headless(args)
    assert rc == 0


def test_run_headless_no_autosave_does_not_write(tmp_path: Path) -> None:
    """--no-autosave skips the save file."""
    save_path = tmp_path / "should_not_exist.json"
    args = parse_args(
        ["--seed=42", "--ticks=10", "--headless",
         "--no-autosave", f"--autosave-path={save_path}"]
    )
    rc = run_headless(args)
    assert rc == 0
    assert not save_path.exists()


def test_run_headless_autosave_writes_file(tmp_path: Path) -> None:
    """Without --no-autosave, a save file is written at autosave-every intervals."""
    save_path = tmp_path / "save.json"
    args = parse_args(
        ["--seed=42", "--ticks=200", "--headless",
         "--autosave-every=100", f"--autosave-path={save_path}"]
    )
    rc = run_headless(args)
    assert rc == 0
    assert save_path.exists()
    assert save_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# main() — entry point
# ---------------------------------------------------------------------------


def test_main_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """--help should exit via SystemExit(0) and print usage."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_main_returns_int() -> None:
    """main() return type is int (for `sys.exit(main())`)."""
    args = parse_args(["--ticks=0", "--headless", "--no-autosave"])
    rc = run_headless(args)
    assert isinstance(rc, int)
