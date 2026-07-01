"""htop-tycoon v3.0 — key-binding package (spec §4.1).

Public surface: ``Binding`` dataclass, ``BINDINGS`` list, and
``validate_bindings`` (called at import time per spec §6: collisions
raise at module load).
"""
from htop_tycoon.bindings.registry import BINDINGS, Binding, validate_bindings

__all__ = ["BINDINGS", "Binding", "validate_bindings"]
