"""T1.1 RED: nice_value(job, level) -> str."""

from __future__ import annotations

from htop_tycoon.domain.enums import Job
from htop_tycoon.ui.widgets.org_tree import nice_value


def test_nice_value_lead_5() -> None:
    assert nice_value(Job.LEAD, 5) == "LEAD 5"


def test_nice_value_junior_1() -> None:
    assert nice_value(Job.JUNIOR, 1) == "JUNIOR 1"


def test_nice_value_designer_7() -> None:
    assert nice_value(Job.DESIGNER, 7) == "DESIGNER 7"


def test_nice_value_qa_3() -> None:
    assert nice_value(Job.QA, 3) == "QA 3"


def test_nice_value_sound_engineer_2() -> None:
    assert nice_value(Job.SOUND_ENGINEER, 2) == "SOUND_ENGINEER 2"
