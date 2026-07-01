"""htop-tycoon v3.0 — OrgTree widget (spec §4.1).

Hierarchical tree of departments and their employees. Renders as a
plain-text tree (no external library) because Tree widget styling is
non-trivial in Textual and a plain indented view is sufficient for
the spec §4.1 'OrgTree' requirement.

Spec §1.3 / §2.1: starts with 경영(Management) + 기획(Planning) unlocked.
"""
from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

from htop_tycoon.domain import Department, GameState

_DEPT_KO: dict[Department, str] = {
    Department.MANAGEMENT: "경영",
    Department.PLANNING: "기획",
    Department.DEVELOPMENT: "개발",
    Department.ART: "아트",
    Department.SOUND: "사운드",
}


class OrgTree(Static):
    """Spec §4.1: 'F5 t — 부서 트리 토글 (toggle department tree)'."""

    DEFAULT_CSS = """
    OrgTree {
        height: 1fr;
        background: $surface;
        color: $foreground;
        padding: 0 1;
        border: solid $primary;
    }
    """

    state: reactive[GameState | None] = reactive(None, always_update=True)

    def watch_state(self, _: GameState | None) -> None:
        self.refresh()

    def render(self) -> str:
        if self.state is None:
            return "[dim italic]부서 트리 — 데이터 없음[/]"
        # Group employees by department
        by_dept: dict[Department, list[str]] = {d: [] for d in Department}
        for emp in self.state.employees:
            by_dept[emp.dept].append(emp.name)
        lines: list[str] = ["[bold]부서 트리 (OrgTree)[/]"]
        for dept in Department:
            if not dept.unlocked_at_start and len(by_dept[dept]) == 0:
                # Skip departments that are locked AND empty.
                # (Spec §1.3: only 경영 + 기획 are unlocked at start.)
                continue
            label = _DEPT_KO.get(dept, dept.name)
            status = "[green]unlocked[/]" if dept.unlocked_at_start else "[dim]locked[/]"
            lines.append(f"  📁 [bold]{label}[/] ({dept.name}) {status}")
            for name in by_dept[dept]:
                lines.append(f"    └─ {name}")
            if not by_dept[dept]:
                lines.append("    └─ [dim italic](empty)[/]")
        return "\n".join(lines)


__all__ = ["OrgTree"]
