"""T1.2 RED: compute_employee_productivity."""

from __future__ import annotations

from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.enums import Department, Job
from htop_tycoon.domain.ids import EmployeeId
from htop_tycoon.domain.money import Money
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine.productivity import compute_employee_productivity


def _emp(**kwargs: object) -> Employee:
    defaults: dict[str, object] = {
        "id": EmployeeId(1),
        "name": "Ada",
        "job": Job.JUNIOR,
        "level": 1,
        "salary": Money(3000_00),
        "satisfaction": 80,
        "dept": Department.DEV,
    }
    defaults.update(kwargs)
    return Employee(**defaults)  # type: ignore[arg-type]


def test_productivity_in_range() -> None:
    rng = GameRng(0)
    p = compute_employee_productivity(_emp(), rng)
    assert 0.0 <= p <= 1.5


def test_satisfaction_zero_yields_zero() -> None:
    """Zombie employees produce nothing."""
    rng = GameRng(0)
    p = compute_employee_productivity(_emp(satisfaction=0), rng)
    assert p == 0.0


def test_high_tier_high_level_high_satisfaction_near_max() -> None:
    """LEAD, level 10, satisfaction 100, rng.max jitter → near max."""
    rng = GameRng(0)
    p = compute_employee_productivity(
        _emp(job=Job.LEAD, level=10, satisfaction=100), rng
    )
    # tier=3/3 * level=10/10 * sat=100/100 * jitter in [0.9, 1.1]
    # max = 1.0 * 1.0 * 1.0 * 1.1 = 1.1
    assert 0.85 <= p <= 1.15


def test_jitter_within_90_to_110_percent() -> None:
    """Jitter is rng-driven in [0.9, 1.1] — productivity varies by ±10%."""
    rng = GameRng(7)
    samples = [compute_employee_productivity(_emp(), rng) for _ in range(200)]
    non_jitter = 1 / 3 * 1 / 10 * 80 / 100  # tier=1/3 * level=1/10 * sat=80/100
    min_expected = non_jitter * 0.9
    max_expected = non_jitter * 1.1
    eps = 1e-9
    assert all(min_expected - eps <= s <= max_expected + eps for s in samples), (
        f"Jitter bounds violated. samples[0]={samples[0]:.3f}, "
        f"min_expected={min_expected:.3f}, max_expected={max_expected:.3f}"
    )


def test_pure_function_determinism() -> None:
    """Same employee + same rng = same productivity."""
    rng_a = GameRng(42)
    rng_b = GameRng(42)
    emp = _emp()
    assert compute_employee_productivity(emp, rng_a) == compute_employee_productivity(emp, rng_b)


def test_different_seeds_diverge() -> None:
    """Different seeds should produce at least one differing value over a window."""
    emp = _emp()
    a = [compute_employee_productivity(emp, GameRng(1)) for _ in range(20)]
    b = [compute_employee_productivity(emp, GameRng(2)) for _ in range(20)]
    assert a != b
