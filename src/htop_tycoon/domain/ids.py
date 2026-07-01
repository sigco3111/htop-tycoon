"""htop-tycoon v3.0 — opaque ID types for domain entities.

Spec §5.3: GameState is the single serialization boundary. All other domain
types (including these IDs) are opaque to the rest of the engine. NewType
keeps the static type-checker honest while staying zero-cost at runtime.

Why NewType (and not frozen dataclasses)?
  - NewType is purely a typing-time concept; at runtime the IDs are just
    ``str``. This keeps the domain layer lightweight and avoids bringing
    dataclass machinery into a layer that should remain a thin façade.
  - Future-proofing for serialization (T33+): if we later need each ID to
    carry metadata (e.g. creation tick, origin entity kind), swap the
    NewType for a frozen dataclass. The factory functions defined here
    become the single point of change for that migration.

Determinism note:
  UUIDs are NOT gameplay-random. Per AGENTS.md, the "no bare random.*"
  invariant targets gameplay determinism (``GameRNG`` is the only allowed
  gateway for engine randomness). UUID4 uses ``os.urandom`` (the OS CSPRNG)
  and is appropriate for opaque entity identifiers. UUIDs themselves are
  never used to seed or replay gameplay — only to distinguish entities.
"""
from __future__ import annotations

import uuid
from typing import NewType

# ---------------------------------------------------------------------------
# Opaque ID types — zero-cost at runtime, typed at type-check time.
# ---------------------------------------------------------------------------

EntityId = NewType("EntityId", str)
"""Generic opaque ID base type. Concrete IDs specialize this."""

EmployeeId = NewType("EmployeeId", str)
ProjectId = NewType("ProjectId", str)
ConsoleId = NewType("ConsoleId", str)
GenreId = NewType("GenreId", str)
ThemeId = NewType("ThemeId", str)
PlatformId = NewType("PlatformId", str)
DeptId = NewType("DeptId", str)


# ---------------------------------------------------------------------------
# Factory functions — all return a fresh UUID4 string wrapped in the
# matching NewType. These are the single point where UUIDs enter the
# domain layer.
# ---------------------------------------------------------------------------

def _new_uuid4_str() -> str:
    """Generate a fresh UUID4 string. Centralized so migration to UUID5 /
    custom IDs later only changes one spot.
    """
    return str(uuid.uuid4())


def new_employee_id() -> EmployeeId:
    """Create a fresh employee identifier."""
    return EmployeeId(_new_uuid4_str())


def new_project_id() -> ProjectId:
    """Create a fresh game-project identifier."""
    return ProjectId(_new_uuid4_str())


def new_console_id() -> ConsoleId:
    """Create a fresh console identifier (used for runtime-instantiated
    consoles; the 3 default consoles ship with fixed IDs in consoles.yaml).
    """
    return ConsoleId(_new_uuid4_str())


def new_genre_id() -> GenreId:
    """Create a fresh genre identifier (rarely used at runtime — genres
    ship as static config in data/genres.yaml).
    """
    return GenreId(_new_uuid4_str())


def new_theme_id() -> ThemeId:
    """Create a fresh theme identifier (rarely used at runtime — themes
    ship as static config in data/themes.yaml).
    """
    return ThemeId(_new_uuid4_str())


def new_platform_id() -> PlatformId:
    """Create a fresh platform identifier (used for the dynamic own-console
    instance after Secret ending).
    """
    return PlatformId(_new_uuid4_str())


def new_dept_id() -> DeptId:
    """Create a fresh department identifier (used only when custom departments
    become a thing post-v3.0; here for forward-compatibility).
    """
    return DeptId(_new_uuid4_str())


__all__ = [
    "ConsoleId",
    "DeptId",
    "EmployeeId",
    "EntityId",
    "GenreId",
    "PlatformId",
    "ProjectId",
    "ThemeId",
    "new_console_id",
    "new_dept_id",
    "new_employee_id",
    "new_genre_id",
    "new_platform_id",
    "new_project_id",
    "new_theme_id",
]
