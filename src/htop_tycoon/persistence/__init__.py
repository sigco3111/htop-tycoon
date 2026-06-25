"""Persistence package for htop-tycoon (T27+).

Owns JSON serialize/deserialize, atomic save with backup-on-write, and
corruption-recovery flows. The state boundary is here: the engine produces
``GameState``, this package writes/reads it, and the UI never mutates
state directly.

Submodules:
- ``serialize`` (T27): ``serialize`` / ``save`` with atomic write + backup.
- ``deserialize`` (T28): ``deserialize`` + safe corruption recovery.
"""
