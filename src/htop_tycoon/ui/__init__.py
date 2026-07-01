"""htop-tycoon v3.0 — Textual UI layer (spec §4).

This package hosts the main App + widgets + screens. Subpackages:
- ``ui.widgets`` — header, footer, metric bar, employee table, org tree,
  strategy status (reactive widgets reading from ``GameState``).
- ``ui.screens`` — modal screens: strategy picker, game starter, employee
  panel, archive, ending.

All widgets are pure Textual: no direct engine calls (spec §5.3 — engine
imports from UI is forbidden; engine emits ``Event`` objects and the UI
consumes them).
"""
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.theme import HTOPTYCOON_THEME

__all__ = ["HTOPTYCOON_THEME", "HtopTycoonApp"]
