"""S5 contract: `python -m htop_tycoon --help` exits 0 with 'htop-tycoon' in stdout.

This is a subprocess test so it exercises the actual entry point that users
will invoke. Fails until src/htop_tycoon/__main__.py exists with argparse.
"""

from __future__ import annotations

import re
import subprocess
import sys


def test_module_help() -> None:
    """`python -m htop_tycoon --help` must exit 0 and mention 'htop-tycoon'."""
    result = subprocess.run(
        [sys.executable, "-m", "htop_tycoon", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, (
        f"`python -m htop_tycoon --help` exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "htop-tycoon" in result.stdout, (
        f"--help stdout missing 'htop-tycoon'. Got:\n{result.stdout}"
    )


def test_module_version() -> None:
    """`python -m htop_tycoon --version` must print '3.0.0'."""
    result = subprocess.run(
        [sys.executable, "-m", "htop_tycoon", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, (
        f"`--version` exited {result.returncode}.\nstderr: {result.stderr}"
    )
    assert "3.0.0" in result.stdout, (
        f"--version stdout missing '3.0.0'. Got:\n{result.stdout}"
    )


def test_module_headless_smoke_runs_three_ticks() -> None:
    """`python -m htop_tycoon --headless --seed 42` runs 3 ticks and exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "htop_tycoon", "--headless", "--seed", "42"],
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, (
        f"--headless exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "headless smoke test" in result.stdout, (
        f"--headless stdout missing smoke test header. Got:\n{result.stdout}"
    )
    assert "tick 1" in result.stdout
    assert "tick 3" in result.stdout
    assert "Headless smoke complete" in result.stdout


def test_module_headless_deterministic_with_seed() -> None:
    """Same seed produces identical cash trajectory across runs."""
    a = subprocess.run(
        [sys.executable, "-m", "htop_tycoon", "--headless", "--seed", "42"],
        capture_output=True, text=True, timeout=15,
    )
    b = subprocess.run(
        [sys.executable, "-m", "htop_tycoon", "--headless", "--seed", "42"],
        capture_output=True, text=True, timeout=15,
    )
    cash_a = re.findall(r"cash=\d+", a.stdout)
    cash_b = re.findall(r"cash=\d+", b.stdout)
    assert cash_a == cash_b and len(cash_a) == 3, (
        f"Deterministic seed 42 must produce identical cash per tick.\n"
        f"Run A: {cash_a}\nRun B: {cash_b}"
    )
