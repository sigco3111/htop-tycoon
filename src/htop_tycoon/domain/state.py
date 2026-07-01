"""htop-tycoon v3.0 — GameState aggregate root. Spec §5.3, §7.3.

The **single serialization boundary** for the entire game. Immutable
updates flow exclusively through ``dataclasses.replace(state, **changes)``.
``compute_hash()`` is deterministic — identical state inputs produce identical
digests — which is the contract enforced by the spec §7.3 frozen-hash
regression tests (``seed=42 → day 100`` / ``1000`` / ``3650``).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.ending import Ending
from htop_tycoon.domain.enums import Department  # local to avoid cycles in employees_by_dept
from htop_tycoon.domain.event import Event
from htop_tycoon.domain.legacy import LegacyScore
from htop_tycoon.domain.market import Market
from htop_tycoon.domain.project import GameProject

# Spec §5.3 frozen-hash support (spec §7.3).
DEFAULT_RNG_SEED: int = 42
# mirror of balance.yaml cash.starting_cash (kept in sync; data loader
# will override in Wave 5+)
DEFAULT_STARTING_CASH: int = 50000


def _canonicalize(obj: Any) -> Any:
    """Recursively convert GameState (and nested types) to a hash-stable form.

    - Frozen dataclasses → dict of field-name → recursively-canonicalized value.
    - Mapping / MappingProxyType → dict (keys are sorted at this level — note
      that ``json.dumps(sort_keys=True)`` also re-sorts, so this is belt +
      braces).
    - List / tuple → list (preserves order; stable because every layer above
      appends in deterministic order).
    - Leaves (str, int, float, bool, None) → unchanged. NewType str wrappers
      are runtime-strings; UUIDs are 36-char str; no special handling needed.
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _canonicalize(getattr(obj, f.name))
                for f in dataclasses.fields(obj)}
    if isinstance(obj, MappingProxyType) or isinstance(obj, Mapping):
        return {k: _canonicalize(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(v) for v in obj]
    return obj


def compute_game_state_hash(state: GameState) -> str:
    """SHA-256 hex digest of the canonical serialization of the state.

    Spec §7.3 contract: same ``seed=42``, same game-day → identical hash.
    Returned as 64-char lowercase hex.
    """
    canonical = _canonicalize(state)
    payload = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class GameState:
    """The aggregate root. Spec §5.3 + §2.2 step 1.

    Frozen; the only mutation path is :func:`dataclasses.replace`.
    """

    # --- Counter & company-wide scalars ---
    day: int = 0
    cash: int = DEFAULT_STARTING_CASH
    fans: int = 0

    # --- Domain collections ---
    employees: tuple[Employee, ...] = field(default_factory=tuple)
    projects: tuple[GameProject, ...] = field(default_factory=tuple)
    market: Market = field(default_factory=Market)

    # --- Persistent records ---
    legacy: LegacyScore = field(default_factory=LegacyScore)
    ending: Ending | None = None

    # --- Determinism (spec §5.3 / §7.3) ---
    rng_seed: int = DEFAULT_RNG_SEED

    # --- Event bus (UI re-renders from snapshot per spec §5.3) ---
    events: tuple[Event, ...] = field(default_factory=tuple)

    # --- Pure helpers --------------------------------------------------

    def compute_hash(self) -> str:
        """Deterministic hash for spec §7.3 frozen-state regression tests."""
        return compute_game_state_hash(self)

    def replace(self, **changes: Any) -> GameState:
        """Friendly wrapper around :func:`dataclasses.replace`."""
        return dataclasses.replace(self, **changes)

    # --- Derived views --------------------------------------------------

    def employees_by_dept(self, dept: Department) -> tuple[Employee, ...]:
        """Return all employees in the given Department."""
        return tuple(e for e in self.employees if e.dept is dept)

    def active_projects(self) -> tuple[GameProject, ...]:
        """Projects still in development (``progress_pct < 100``)."""
        return tuple(p for p in self.projects if not p.is_complete)

    def released_projects(self) -> tuple[GameProject, ...]:
        """Projects with a release action executed (``released_day`` set)."""
        return tuple(p for p in self.projects if p.is_released)


__all__ = [
    "DEFAULT_RNG_SEED",
    "DEFAULT_STARTING_CASH",
    "GameState",
    "compute_game_state_hash",
]
