"""HireScreen modal data — shows N candidates to hire from."""

from __future__ import annotations

from htop_tycoon.engine.hr import HireCandidate


class HireScreen:
    """Modal data holder listing hire candidates.

    render() returns formatted text with numbered list.
    select(idx) returns the picked candidate or None if idx out of range.
    """

    __slots__ = ("_candidates",)

    def __init__(self, candidates: list[HireCandidate]) -> None:
        self._candidates = list(candidates)

    @property
    def candidates(self) -> list[HireCandidate]:
        return self._candidates

    def render(self) -> str:
        lines = [f"Hire (pick 1-{len(self._candidates)})", ""]
        for idx, c in enumerate(self._candidates, start=1):
            lines.append(
                f"{idx}. {c.name:<10} {c.job.value:<14} L{c.suggested_level:<2} "
                f"{c.department.value:<6} {c.monthly_salary}/mo"
            )
        lines.append("")
        lines.append(f"Press 1-{len(self._candidates)} to hire, 'h' to close.")
        return "\n".join(lines)

    def select(self, idx: int) -> HireCandidate | None:
        if 1 <= idx <= len(self._candidates):
            return self._candidates[idx - 1]
        return None
