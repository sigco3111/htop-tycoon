"""OrgTree widget — htop-style department tree with employee roster.

Phase 2C. The widget groups CompanyState.employees by Department, shows
each employee with their nice_value (job + level), satisfaction, salary,
and a zombie flag when satisfaction < 20.
"""

from __future__ import annotations

from htop_tycoon.domain.enums import Job


def nice_value(job: Job, level: int) -> str:
    """htop-style 'nice value' — job tier name + numeric level."""
    return f"{job.value} {level}"
