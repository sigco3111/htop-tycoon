"""MetricBar widget — htop-style 4-axis quality bars for active project.

Phase 2D. Reads the active GameProject (lowest progress) from injected
CompanyState and renders 4 horizontal ASCII bars: FUN, GRAPHICS,
SOUND, ORIGINAL. Each bar uses unicode block chars (█ filled, ░ empty).
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from htop_tycoon.domain import CompanyState, GameProject

FILLED_CHAR: str = "█"
EMPTY_CHAR: str = "░"
DEFAULT_BAR_WIDTH: int = 10

AXIS_LABELS: tuple[tuple[str, str], ...] = (
    ("FUN", "metric-fun"),
    ("GRAPHICS", "metric-graphics"),
    ("SOUND", "metric-sound"),
    ("ORIGINAL", "metric-original"),
)

EMPTY_PROJECT_LABEL: str = "(no active project)"


def bar(value: int, width: int = DEFAULT_BAR_WIDTH) -> str:
    """Render an ASCII progress bar: value/100 as filled block ratio."""
    filled = int(value / 100 * width)
    empty = width - filled
    return FILLED_CHAR * filled + EMPTY_CHAR * empty


def _pick_active_project(state: CompanyState) -> GameProject | None:
    """Return the in-progress project with lowest progress (or None)."""
    if not state.projects:
        return None
    return min(state.projects.values(), key=lambda p: p.progress.value)


def _format_axis(label: str, value: int) -> str:
    return f"{label:<8} {bar(value)} {value:>3}"


class MetricBar(Vertical):
    """htop-style 4-axis quality bar for the active project."""

    DEFAULT_CSS: ClassVar[str] = """
    MetricBar {
        height: auto;
        background: $background;
        color: $primary;
        padding: 0 1;
    }

    MetricBar Static {
        height: 1;
    }
    """

    def __init__(self, state: CompanyState) -> None:
        super().__init__()
        self._state = state
        self._active = _pick_active_project(state)

    def compose(self) -> ComposeResult:
        if self._active is None:
            yield Static(EMPTY_PROJECT_LABEL)
            return
        quality = self._active.quality
        values = (
            quality.fun,
            quality.graphics,
            quality.sound,
            quality.originality,
        )
        for (label, _widget_id), value in zip(AXIS_LABELS, values, strict=True):
            yield Static(_format_axis(label, value))
