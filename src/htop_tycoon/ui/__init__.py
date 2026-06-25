"""htop_tycoon.ui — Textual TUI layer.

UI is a strictly read-only consumer of GameState: it renders the locked
layout (header / metrics / org-tree / employee-panel / alerts / footer)
and forwards engine events into widget state via the EventBus. UI handlers
must NEVER mutate ``self.state`` directly; only the engine produces new
states.
"""

from __future__ import annotations

from htop_tycoon.ui.app import HtopTycoonApp

__all__ = ["HtopTycoonApp"]
