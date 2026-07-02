"""mock_state — deterministic CompanyState factory for UI demo / pilot tests.

Returns a CompanyState with 6 employees across 4 departments (including
one zombie QA) and 1 in-development RPG project. Used by the OrgTree
pilot test and as the default fallback when HtopTycoonApp is constructed
without an explicit state.
"""

from __future__ import annotations

from htop_tycoon.domain import (
    CompanyState,
    Department,
    Employee,
    EmployeeId,
    GameProject,
    GameTitle,
    Genre,
    Job,
    Money,
    Platform,
    Progress,
    ProjectId,
    QualityAxes,
    StrategyKind,
    compute_salary,
)


def mock_state(speed: int = 0) -> CompanyState:
    """Build the canonical demo CompanyState used by UI tests.

    speed=0 (paused) by default so Pilot tests don't trigger the timer.
    Pass speed=1/2/3 to simulate an actively-running game.
    """
    state = CompanyState(
        cash=Money(100_000_00),
        fans=0,
        strategy=StrategyKind.BALANCED,
        year=1,
        day_index=0,
    )
    state = state.set_speed(speed)

    ada = Employee(
        id=EmployeeId(1),
        name="Ada",
        job=Job.LEAD,
        level=5,
        salary=compute_salary(Job.LEAD, 5).amount,
        satisfaction=85,
        dept=Department.DEV,
    )
    bob = Employee(
        id=EmployeeId(2),
        name="Bob",
        job=Job.JUNIOR,
        level=2,
        salary=compute_salary(Job.JUNIOR, 2).amount,
        satisfaction=70,
        dept=Department.DEV,
    )
    carol = Employee(
        id=EmployeeId(3),
        name="Carol",
        job=Job.DESIGNER,
        level=4,
        salary=compute_salary(Job.DESIGNER, 4).amount,
        satisfaction=75,
        dept=Department.ART,
    )
    dave = Employee(
        id=EmployeeId(4),
        name="Dave",
        job=Job.SOUND_ENGINEER,
        level=3,
        salary=compute_salary(Job.SOUND_ENGINEER, 3).amount,
        satisfaction=80,
        dept=Department.SOUND,
    )
    eve = Employee(
        id=EmployeeId(5),
        name="Eve",
        job=Job.QA,
        level=2,
        salary=compute_salary(Job.QA, 2).amount,
        satisfaction=15,
        dept=Department.QA,
    )
    frank = Employee(
        id=EmployeeId(6),
        name="Frank",
        job=Job.QA,
        level=4,
        salary=compute_salary(Job.QA, 4).amount,
        satisfaction=70,
        dept=Department.QA,
    )

    for emp in (ada, bob, carol, dave, eve, frank):
        state = state.add_employee(emp)

    project = GameProject(
        id=ProjectId(1),
        title=GameTitle("Eldritch Quest"),
        genre=Genre.RPG,
        platform=Platform.PC,
        console=None,
        progress=Progress(42),
        quality=QualityAxes(60, 40, 30, 50),
        days_in_dev=42,
        lead_id=EmployeeId(1),
        team_ids=(EmployeeId(1), EmployeeId(2)),
    )
    state = state.add_project(project)

    return state
