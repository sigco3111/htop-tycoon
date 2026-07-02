"""ReleaseScreen modal — show shipped projects to release."""

from __future__ import annotations

from htop_tycoon.domain import CompanyState, GameProject, ProjectId


class ReleaseScreen:
    """Modal data holder for project release selection.

    Lists shipped projects. select(idx) returns ProjectId or None.
    """

    __slots__ = ("_projects",)

    def __init__(self, state: CompanyState) -> None:
        self._projects = [p for p in state.projects.values() if p.is_shipped]

    @property
    def projects(self) -> tuple[GameProject, ...]:
        return tuple(self._projects)

    def render(self) -> str:
        if not self._projects:
            return "Release: no shipped projects available.\nShip a project first (progress >= 100)."
        lines = [f"Release (pick 1-{len(self._projects)})", ""]
        for idx, p in enumerate(self._projects, start=1):
            lines.append(
                f"{idx}. {str(p.title):<20} {p.genre.value:<10} "
                f"Q:{p.quality.sum()}/400 days:{p.days_in_dev}"
            )
        lines.append("")
        lines.append(f"Press 1-{len(self._projects)} to release on console, 'esc' to cancel.")
        return "\n".join(lines)

    def select(self, idx: int) -> ProjectId | None:
        if 1 <= idx <= len(self._projects):
            return self._projects[idx - 1].id
        return None
