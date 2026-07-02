"""FireScreen modal data — shows current employees sorted by lowest satisfaction."""

from __future__ import annotations

from htop_tycoon.domain import CompanyState, Employee, EmployeeId


class FireScreen:
    """Modal data holder listing employees to fire.

    Sorted by satisfaction ascending (zombies first), then by id.
    select(idx) returns the picked EmployeeId or None if idx out of range.
    """

    __slots__ = ("_ordered",)

    MAX_VISIBLE: int = 9

    def __init__(self, state: CompanyState) -> None:
        self._ordered: list[Employee] = sorted(
            state.employees.values(),
            key=lambda e: (e.satisfaction, int(e.id)),
        )

    @property
    def ordered(self) -> list[Employee]:
        return self._ordered

    def render(self) -> str:
        visible = self._ordered[: self.MAX_VISIBLE]
        lines = [f"Fire (pick 1-{len(visible)}, lowest sat first)", ""]
        for idx, e in enumerate(visible, start=1):
            zombie = " [ZOMBIE]" if e.is_zombie else ""
            lines.append(
                f"{idx}. {e.name:<10} {e.job.value:<14} L{e.level:<2} "
                f"sat:{e.satisfaction}%{zombie}"
            )
        lines.append("")
        lines.append(
            f"Press 1-{len(visible)} to fire, 'x' to close."
        )
        return "\n".join(lines)

    def select(self, idx: int) -> EmployeeId | None:
        if 1 <= idx <= min(len(self._ordered), self.MAX_VISIBLE):
            return self._ordered[idx - 1].id
        return None
