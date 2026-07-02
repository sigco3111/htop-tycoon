"""T2.2 RED: compute_sales_revenue."""

from __future__ import annotations

from htop_tycoon.domain.enums import Console, Genre, Platform
from htop_tycoon.domain.ids import GameTitle, ProjectId
from htop_tycoon.domain.money import Money
from htop_tycoon.domain.project import GameProject
from htop_tycoon.domain.quality import Progress, QualityAxes
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine.market import MarketState
from htop_tycoon.engine.sales import compute_sales_revenue


def _project(**kwargs: object) -> GameProject:
    defaults: dict[str, object] = {
        "id": ProjectId(1),
        "title": GameTitle("Test"),
        "genre": Genre.RPG,
        "platform": Platform.PC,
        "console": None,
        "progress": Progress(100),
        "quality": QualityAxes(50, 50, 50, 50),
        "days_in_dev": 100,
        "lead_id": None,
        "team_ids": (),
    }
    defaults.update(kwargs)
    return GameProject(**defaults)  # type: ignore[arg-type]


def test_sales_revenue_non_negative() -> None:
    market = MarketState.default_for_platform(Platform.PC)
    rev = compute_sales_revenue(_project(), market, GameRng(0))
    assert isinstance(rev, Money)
    assert rev.cents >= 0


def test_sales_revenue_zero_quality_yields_zero() -> None:
    """quality all 0 → revenue = 0."""
    market = MarketState.default_for_platform(Platform.PC)
    rev = compute_sales_revenue(_project(quality=QualityAxes(0, 0, 0, 0)), market, GameRng(0))
    assert rev.cents == 0


def test_sales_revenue_max_quality_high_revenue() -> None:
    """quality all 100 → revenue > 0 and reasonably large."""
    market = MarketState.default_for_platform(Platform.PC)
    rev = compute_sales_revenue(_project(quality=QualityAxes(100, 100, 100, 100)), market, GameRng(0))
    assert rev.cents > 0
    # 10000 units * 1.0 pop * 1.1 genre * 1.0 quality/400 * 1.0 trend * ~1.0 jitter * $30/unit
    # = ~$330,000 ~= 33_000_000 cents
    assert rev.cents > 10_000_000


def test_sales_revenue_higher_popularity_more_revenue() -> None:
    """MOBILE (pop 1.3) yields more revenue than HANDHELD (pop 0.6)."""
    proj = _project()
    mobile = MarketState.default_for_platform(Platform.MOBILE)
    handheld = MarketState.default_for_platform(Platform.HANDHELD)
    rev_mobile = compute_sales_revenue(proj, mobile, GameRng(0))
    rev_handheld = compute_sales_revenue(proj, handheld, GameRng(0))
    assert rev_mobile.cents > rev_handheld.cents


def test_sales_revenue_console_popularity_applied() -> None:
    """Console.PIXEL_2 (pop 1.2) outperforms Console.ATARI_Q (pop 0.6)."""
    proj = _project(platform=Platform.CONSOLE, console=Console.PIXEL_2)
    pixel = MarketState(console=Console.PIXEL_2, platform=Platform.CONSOLE, popularity=1.2, trend=1.0)
    atari = MarketState(console=Console.ATARI_Q, platform=Platform.CONSOLE, popularity=0.6, trend=1.0)
    rev_pixel = compute_sales_revenue(proj, pixel, GameRng(0))
    rev_atari = compute_sales_revenue(proj, atari, GameRng(0))
    assert rev_pixel.cents > rev_atari.cents


def test_sales_revenue_genre_factor_applied() -> None:
    """ACTION (1.2) yields more revenue than PUZZLE (0.9) with high quality."""
    market = MarketState.default_for_platform(Platform.PC)
    rev_action = compute_sales_revenue(
        _project(genre=Genre.ACTION, quality=QualityAxes(100, 100, 100, 100)),
        market,
        GameRng(0),
    )
    rev_puzzle = compute_sales_revenue(
        _project(genre=Genre.PUZZLE, quality=QualityAxes(100, 100, 100, 100)),
        market,
        GameRng(0),
    )
    assert rev_action.cents > rev_puzzle.cents


def test_sales_revenue_deterministic_with_seed() -> None:
    market = MarketState.default_for_platform(Platform.PC)
    proj = _project()
    a = compute_sales_revenue(proj, market, GameRng(42))
    b = compute_sales_revenue(proj, market, GameRng(42))
    assert a.cents == b.cents


def test_sales_revenue_trend_applied() -> None:
    """Higher trend → higher revenue (with same rng seed and project)."""
    proj = _project()
    trend_low = MarketState(None, Platform.PC, popularity=1.0, trend=0.5)
    trend_high = MarketState(None, Platform.PC, popularity=1.0, trend=2.0)
    rev_low = compute_sales_revenue(proj, trend_low, GameRng(0))
    rev_high = compute_sales_revenue(proj, trend_high, GameRng(0))
    assert rev_high.cents > rev_low.cents


def test_sales_revenue_pure_function() -> None:
    """Calling twice with same args yields identical revenue."""
    market = MarketState.default_for_platform(Platform.PC)
    proj = _project()
    first = compute_sales_revenue(proj, market, GameRng(7))
    second = compute_sales_revenue(proj, market, GameRng(7))
    assert first.cents == second.cents
