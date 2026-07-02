"""S5 contract: `python -m htop_tycoon --help` exits 0 with 'htop-tycoon' in stdout.

This is a subprocess test so it exercises the actual entry point that users
will invoke. Fails until src/htop_tycoon/__main__.py exists with argparse.
"""

from __future__ import annotations

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
