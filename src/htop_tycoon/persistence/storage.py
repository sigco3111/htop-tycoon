"""Persistence storage: atomic writes + backup rotation + save/load helpers."""

from __future__ import annotations

from pathlib import Path

from htop_tycoon.domain import CompanyState
from htop_tycoon.persistence.serialize import from_yaml, to_yaml

BACKUP_EXTENSION: str = ".yaml"


def atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically: tmp file + os.replace.

    Guarantees: no torn writes; no leftover .tmp on success.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def rotate_backups(directory: Path, base_name: str, keep: int = 3) -> None:
    """Shift backup chain before a new save.

    Convention: `base_name.yaml` is live. `base_name.1.yaml` is newest
    backup, `.2.yaml` next, etc. After rotation at most `keep - 1` backups
    exist plus the live file (total `keep` files).
    """
    if keep < 1:
        raise ValueError(f"keep must be >= 1, got {keep}")
    extras = keep - 1
    if extras == 0:
        return
    # Drop the oldest if chain is full: .N.yaml -> delete
    oldest = directory / f"{base_name}.{extras}{BACKUP_EXTENSION}"
    if oldest.exists():
        oldest.unlink()
    # Shift numbered backups from highest to lowest so we never clobber.
    for i in range(extras - 1, 0, -1):
        src = directory / f"{base_name}.{i}{BACKUP_EXTENSION}"
        if src.exists():
            dst = directory / f"{base_name}.{i + 1}{BACKUP_EXTENSION}"
            src.replace(dst)
    # Promote live save to .1.yaml.
    live = directory / f"{base_name}{BACKUP_EXTENSION}"
    if live.exists():
        first_backup = directory / f"{base_name}.1{BACKUP_EXTENSION}"
        live.replace(first_backup)


def save_state(state: CompanyState, path: Path) -> None:
    """Rotate previous backups then atomically write new save."""
    rotate_backups(path.parent, path.stem)
    atomic_write(path, to_yaml(state))


def load_state(path: Path) -> CompanyState:
    """Read YAML save file and reconstruct CompanyState."""
    text = path.read_text(encoding="utf-8")
    return from_yaml(text)
