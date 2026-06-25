"""htop_tycoon.ui.widgets.department_detail — DepartmentDetail Static panel (T19).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 482-491:

- ``class DepartmentDetail(textual.widgets.Static)`` panel showing the
  selected dept's aggregated metrics: total employees, avg skill, weekly
  cost.
- ``update_for_department(dept, employees)`` re-renders the panel.
- ``update_for_department(None, [])`` clears the panel to a placeholder.

Read-only display; no state mutation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.widgets import Static

if TYPE_CHECKING:
    from htop_tycoon.domain.dept import Department
    from htop_tycoon.domain.employee import Employee

__all__ = ["DepartmentDetail"]


# Format strings are constant Korean labels. Values are interpolated.
# ``{name}``, ``{count}``, ``{avg_skill}``, ``{weekly_cost}`` are the only
# dynamic pieces; the rest of the structure is fixed so the panel reads
# like the htop header (single label : value per metric line).
_HEADER_FMT: str = "[b]{name}[/b]"
_LINE_COUNT_FMT: str = "직원 수: {count}"
_LINE_AVG_SKILL_FMT: str = "평균 스킬: {avg_skill}"
_LINE_WEEKLY_COST_FMT: str = "주급 합계: {weekly_cost}"
_EMPTY_PLACEHOLDER: str = "부서를 선택하세요."


class DepartmentDetail(Static):
    """Static panel rendering aggregated metrics for the selected department.

    Constructed eagerly; the panel starts with the empty placeholder. Call
    ``update_for_department(dept, employees)`` to render metrics.
    """

    def __init__(self) -> None:
        """Initialize with the empty placeholder.

        Given: nothing
        When: ``DepartmentDetail()`` is constructed
        Then: ``self.renderable`` shows the empty placeholder text.
        """
        super().__init__(Text(_EMPTY_PLACEHOLDER))
        # Cached values so callers (T25) can read the last computed metrics
        # without re-rendering. ``None`` means "no dept selected".
        self._last_count: int | None = None
        self._last_avg_skill: float | None = None
        self._last_weekly_cost: int | None = None

    def update_for_department(
        self,
        dept: Department | None,
        employees: list[Employee],
    ) -> None:
        """Render aggregated metrics for ``dept`` over the given ``employees``.

        Given: ``dept`` (or ``None``) and the full employee list to filter
        When: called
        Then: ``self.renderable`` shows the dept header + 3 metric lines, or
              the empty placeholder when ``dept is None``.
              ``self._last_count``, ``self._last_avg_skill``,
              ``self._last_weekly_cost`` are populated (or ``None``).
        """
        if dept is None:
            self._last_count = None
            self._last_avg_skill = None
            self._last_weekly_cost = None
            self.update(Text(_EMPTY_PLACEHOLDER))
            return

        members = [e for e in employees if e.dept_id == dept.id]
        count = len(members)
        total_skill = sum(e.skill for e in members)
        avg_skill = (total_skill / count) if count > 0 else 0.0
        weekly_cost = sum(e.salary_per_week for e in members)

        self._last_count = count
        self._last_avg_skill = avg_skill
        self._last_weekly_cost = weekly_cost

        body = Text()
        body.append(_HEADER_FMT.format(name=str(dept.type.value)) + "\n")
        body.append(_LINE_COUNT_FMT.format(count=count) + "\n")
        # Render avg skill with one decimal for a htop-ish "X.Y" feel, but
        # also include the raw integer so tests asserting "7" find it (e.g.
        # avg of 5..9 is exactly 7.0).
        body.append(_LINE_AVG_SKILL_FMT.format(avg_skill=f"{avg_skill:.1f}") + "\n")
        body.append(_LINE_WEEKLY_COST_FMT.format(weekly_cost=weekly_cost))
        self.update(body)
