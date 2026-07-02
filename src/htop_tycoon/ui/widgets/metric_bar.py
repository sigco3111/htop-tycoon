"""htop-tycoon v3.0 — MetricBar widget (spec §4.1).

Renders 4 quality-axis bars for the active game project:
``재미 FUN`` / ``그래픽 GRAPHICS`` / ``사운드 SOUND`` / ``독창성 ORIGINALITY``
each on a 0..10 scale. The active project is ``app.active_project``; if no
project is active, the widget renders an empty-state message.
"""
from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget

from htop_tycoon.domain import GameProject, QualityAxis


def _bar(value: float, width: int = 20) -> str:
    """Render a 0..10 value as a htop-style bar (filled/empty blocks)."""
    clamped = max(0.0, min(10.0, value))
    filled = int(round(clamped / 10.0 * width))
    empty = width - filled
    return "█" * filled + "░" * empty


class MetricBar(Widget):
    """Spec §4.1: '4 metric bars (bottom): Game quality axes: 재미/그래픽/사운드/독창성'."""

    DEFAULT_CSS = """
    MetricBar {
        height: 6;
        background: $background;
        color: $primary;
        padding: 0 1;
    }
    """

    project: reactive[GameProject | None] = reactive(None, always_update=True)

    def watch_project(self, _: GameProject | None) -> None:
        self.refresh()

    def render(self) -> str:
        if self.project is None:
            return "[dim italic]진행 중인 게임 없음[/]"
        axes = self.project.quality_axes or {}
        lines: list[str] = []
        ko = {
            QualityAxis.FUN: "재미",
            QualityAxis.GRAPHICS: "그래픽",
            QualityAxis.SOUND: "사운드",
            QualityAxis.ORIGINALITY: "독창성",
        }
        color = {
            QualityAxis.FUN: "green",
            QualityAxis.GRAPHICS: "#39ff14",
            QualityAxis.SOUND: "magenta",
            QualityAxis.ORIGINALITY: "yellow",
        }
        for axis in QualityAxis:
            value = float(axes.get(axis, 0.0))
            label = ko[axis]
            lines.append(f"[{color[axis]}]{label:6s} {_bar(value)} {value:5.1f}/10[/]")
        return "\n".join(lines)


__all__ = ["MetricBar"]
