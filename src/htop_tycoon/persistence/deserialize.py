"""T28: JSON deserialize + safe corruption recovery (deterministic seed).

This module is the *read* half of the persistence layer. The *write* half
(``serialize`` / ``save``) lives in T27.

Two public functions:

- :func:`deserialize` — convert a v1 envelope (``{"version": 1, "state":
  {...}, "saved_at_iso": "..."}``) back to a :class:`~htop_tycoon.domain.state.GameState`.
  On ANY error (missing key, unknown version, bad field type, malformed
  envelope), log a warning and return :func:`new_game` seeded with
  :data:`CORRUPTION_RECOVERY_SEED`. NEVER raises.
- :func:`load` — read JSON from ``path`` and delegate to :func:`deserialize`.
  On ``json.JSONDecodeError`` from the primary file, tries ``path.with_suffix('.bak')``.
  If the backup also fails to parse, returns the recovery state. On
  ``FileNotFoundError``, returns the recovery state without consulting backup.

The recovery seed is the module-level constant :data:`CORRUPTION_RECOVERY_SEED`
(locked at ``0``). It MUST NOT be derived from ``time.time()`` — that would
break the determinism invariant: recovery must produce the same
``state_hash`` across runs for the same schema version.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from htop_tycoon.domain.state import (
    Company,
    GameState,
    GameTime,
    new_game,
)
from htop_tycoon.persistence.serialize import SCHEMA_VERSION

__all__ = ["CORRUPTION_RECOVERY_SEED", "deserialize", "load"]

# Recovery seed: a fixed constant, NEVER derived from ``time.time()``.
#
# Why a constant? The determinism invariant (see root AGENTS.md) requires
# that ``state_hash(state)`` is fully determined by the state content. If we
# seeded recovery from ``int(time.time())``, two CI runs that hit corruption
# one second apart would produce different ``state_hash`` values, breaking
# any test that pins a "post-corruption" hash.
#
# Locked at 0 for v0.1.0. Changing this is a wave-level decision and requires
# updating ``.omo/plans/htop-tycoon.md``.
CORRUPTION_RECOVERY_SEED: int = 0

_logger = logging.getLogger(__name__)


def _recovery_state() -> GameState:
    """Return a fresh state seeded with :data:`CORRUPTION_RECOVERY_SEED`.

    Centralized so every recovery path produces the exact same state and so
    the determinism invariant has a single source of truth.
    """
    return new_game(CORRUPTION_RECOVERY_SEED)


def deserialize(data: dict[str, Any]) -> GameState:
    """Convert a v1 envelope back to a :class:`GameState`, or return recovery state.

    Contract:

    - Reads ``data["version"]``; if missing, not an int, or not equal to
      :data:`SCHEMA_VERSION`, logs a warning and returns the recovery state.
    - Reads ``data["state"]`` and reconstructs ``Company``, ``GameTime``, and
      ``GameState`` from it. ANY exception during reconstruction
      (``KeyError``, ``TypeError``, ``ValueError``) is caught, logged, and
      converted to the recovery state.
    - On success, returns the reconstructed state (NOT the recovery state).

    This function NEVER raises. It is the single chokepoint that turns
    corrupt JSON into a playable game.
    """
    try:
        # 1. Schema version check. Missing key, wrong type, or wrong value
        #    all funnel into recovery.
        version_raw = data["version"]  # KeyError -> recovery
        if not isinstance(version_raw, int) or isinstance(version_raw, bool):
            _logger.warning(
                "deserialize: version is not a real int (got %r); recovering",
                type(version_raw).__name__,
            )
            return _recovery_state()
        if version_raw != SCHEMA_VERSION:
            _logger.warning(
                "deserialize: unknown schema version %r (expected %d); recovering",
                version_raw,
                SCHEMA_VERSION,
            )
            return _recovery_state()

        # 2. Reconstruct from data["state"]. Any failure here is corruption.
        state_dict = data["state"]  # KeyError -> recovery
        if not isinstance(state_dict, dict):
            _logger.warning(
                "deserialize: 'state' is not a dict (got %s); recovering",
                type(state_dict).__name__,
            )
            return _recovery_state()

        company = Company(**state_dict["company"])  # KeyError/TypeError/ValueError
        game_time = GameTime(**state_dict["game_time"])  # KeyError/ValueError

        return GameState(
            company=company,
            departments=state_dict["departments"],
            employees=state_dict["employees"],
            products=state_dict["products"],
            competitors=state_dict["competitors"],
            events_active=state_dict["events_active"],
            ending_history=state_dict["ending_history"],
            secret_investor_cleared=state_dict["secret_investor_cleared"],
            tick=state_dict["tick"],
            rng_seed=state_dict["rng_seed"],
            game_time=game_time,
            version=state_dict["version"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        # Catch the precise exception family raised by dict-key / type /
        # validator failures. Other exceptions (e.g. RecursionError) are
        # NOT caught — those are bugs in our code, not corruption.
        _logger.warning(
            "deserialize: corruption detected (%s: %s); recovering with seed=%d",
            type(exc).__name__,
            exc,
            CORRUPTION_RECOVERY_SEED,
        )
        return _recovery_state()


def load(path: Path) -> GameState:
    """Load a :class:`GameState` from ``path``, with backup fallback and recovery.

    Order of operations:

    1. Try to read and parse JSON from ``path``.
       - ``FileNotFoundError`` -> return recovery state immediately (no
         backup try; if the primary is missing, the user is on a fresh
         install or has deleted their save, and we should NOT silently
         resurrect a stale backup from a prior run).
       - ``json.JSONDecodeError`` -> try ``path.with_suffix('.bak')``.
         - Backup parses -> :func:`deserialize` it (corrupt-but-valid-JSON
           backup still funnels through recovery inside ``deserialize``).
         - Backup also raises ``json.JSONDecodeError`` or ``FileNotFoundError``
           -> return recovery state.
       - Other ``OSError`` (permission denied, etc.) -> log and recover.
    2. On a successfully-parsed payload, hand it to :func:`deserialize`.
       Corrupt-but-valid-JSON is :func:`deserialize`'s problem, not ours.

    NEVER raises. Always returns a :class:`GameState`.
    """
    try:
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            _logger.warning(
                "load: primary file at %s is not valid JSON (%s); trying backup",
                path,
                exc,
            )
            return _load_from_backup(path, exc)
    except FileNotFoundError:
        _logger.warning("load: primary file at %s not found; recovering", path)
        return _recovery_state()
    except OSError as exc:
        _logger.warning(
            "load: OS error reading %s (%s); recovering", path, exc
        )
        return _recovery_state()

    if not isinstance(data, dict):
        _logger.warning(
            "load: top-level JSON in %s is not a dict (got %s); recovering",
            path,
            type(data).__name__,
        )
        return _recovery_state()

    return deserialize(data)


def _load_from_backup(path: Path, primary_error: json.JSONDecodeError) -> GameState:
    """Try the backup file after primary JSON parse failed.

    Helper for :func:`load`. If the backup also fails to parse, or doesn't
    exist, returns the recovery state. If it parses, hands it to
    :func:`deserialize` so corrupt-but-valid-JSON still funnels through
    the same recovery path as in-memory corruption.
    """
    backup_path = path.with_suffix(".bak")
    try:
        backup_text = backup_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _logger.warning(
            "load: backup file at %s not found; recovering (primary was: %s)",
            backup_path,
            primary_error,
        )
        return _recovery_state()
    except OSError as exc:
        _logger.warning(
            "load: OS error reading backup %s (%s); recovering", backup_path, exc
        )
        return _recovery_state()

    try:
        backup_data = json.loads(backup_text)
    except json.JSONDecodeError as exc:
        _logger.warning(
            "load: backup file at %s is also not valid JSON (%s); recovering",
            backup_path,
            exc,
        )
        return _recovery_state()

    if not isinstance(backup_data, dict):
        _logger.warning(
            "load: backup file at %s top-level is not a dict (got %s); recovering",
            backup_path,
            type(backup_data).__name__,
        )
        return _recovery_state()

    _logger.warning(
        "load: using backup at %s (primary was corrupt: %s)",
        backup_path,
        primary_error,
    )
    return deserialize(backup_data)
