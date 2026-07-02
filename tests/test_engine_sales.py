"""htop-tycoon v3.0 — engine.sales coverage tests. Spec §2.2 step 8, §2.6, §2.7.

Targets ``engine/sales.py`` (currently 49% covered) to push above 80%.

Verifies:
- Combo multiplier lookup (hit + miss paths).
- Sales computation respects quality, popularity, fans, combo.
- Royalty resolution: PC/OWN_CONSOLE pay 0; licensed consoles pay 15%.
- Net revenue = gross × (1 - royalty_rate).
- Unreleased / zero-popularity / zero-quality inputs return (0, 0).
- ``fans_gained_from_sales`` translates copies to fans.
"""
from __future__ import annotations

from htop_tycoon.domain import (
    ConsoleId,
    ConsoleMarket,
    GameProject,
    GameState,
    GenreId,
    Platform,
    PlatformId,
    ProjectId,
    QualityAxis,
    ThemeId,
)
from htop_tycoon.engine.sales import (
    FANS_PER_COPY,
    compute_sales,
    fans_gained_from_sales,
    get_combo_multiplier,
)

# --- helpers --------------------------------------------------------------


def _axes(avg: float) -> dict[QualityAxis, float]:
    return {axis: avg for axis in QualityAxis}


def _released(genre: str = "rpg", theme: str = "fantasy", avg: float = 5.0) -> GameProject:
    """Released project with all axes equal to avg and matching genre/theme."""
    return GameProject(
        id=ProjectId("p"),
        name="Sales Test",
        genre_id=GenreId(genre),
        theme_id=ThemeId(theme),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=100.0,
        released_day=10,
        quality_axes=_axes(avg),
    )


def _unreleased(avg: float = 5.0) -> GameProject:
    """A project in development (released_day is None)."""
    return GameProject(
        id=ProjectId("p"),
        name="In Progress",
        genre_id=GenreId("rpg"),
        theme_id=ThemeId("fantasy"),
        platform_id=PlatformId(Platform.PC.name),
        progress_pct=50.0,
        quality_axes=_axes(avg),
    )


def _console(
    *,
    cid: str = "c1",
    cur_pop: float = 1.0,
    royalty: float = 0.15,
    requires_license: bool = True,
) -> ConsoleMarket:
    return ConsoleMarket(
        id=ConsoleId(cid),
        name_ko="테스트 콘솔",
        base_popularity=1.0,
        release_year=1,
        peak_year=2,
        decline_rate=0.1,
        discontinue_year=None,
        royalty_rate=royalty,
        requires_license=requires_license,
        current_popularity=cur_pop,
    )


def _state(*, fans: int = 0) -> GameState:
    return GameState(rng_seed=42, fans=fans)


# --- get_combo_multiplier -----------------------------------------------


def test_combo_multiplier_hit_returns_mapped_value() -> None:
    """(action, stealth) -> 2.0 per spec §2.7 table."""
    assert get_combo_multiplier("action", "stealth") == 2.0


def test_combo_multiplier_rhythm_music_returns_1_5() -> None:
    """Another table lookup to lock the dict contents."""
    assert get_combo_multiplier("rhythm", "music") == 1.5


def test_combo_multiplier_miss_returns_default_1_0() -> None:
    """Unknown (genre, theme) pair returns neutral 1.0."""
    assert get_combo_multiplier("unknown", "unknown") == 1.0
    assert get_combo_multiplier("rpg", "not_a_real_theme") == 1.0


# --- compute_sales: short-circuit paths ---------------------------------


def test_compute_sales_unreleased_returns_zero() -> None:
    """Unreleased project (released_day is None) -> (0, 0)."""
    state = _state(fans=10_000)
    console = _console(cur_pop=1.0)
    assert compute_sales(state, _unreleased(5.0), console) == (0, 0)


def test_compute_sales_zero_popularity_returns_zero() -> None:
    """Console with cur_popularity == 0 -> (0, 0)."""
    state = _state(fans=10_000)
    console = _console(cur_pop=0.0)
    assert compute_sales(state, _released(avg=8.0), console) == (0, 0)


def test_compute_sales_zero_quality_returns_zero() -> None:
    """Released project with all axes 0.0 -> (0, 0) (zero quality bypass)."""
    state = _state(fans=10_000)
    console = _console(cur_pop=1.0)
    assert compute_sales(state, _released(avg=0.0), console) == (0, 0)


# --- compute_sales: happy paths -----------------------------------------


def test_compute_sales_high_quality_licensed_console_applies_royalty() -> None:
    """High quality on a licensed console -> gross copies > 0 and net < gross."""
    state = _state(fans=10_000)
    console = _console(cur_pop=1.0, royalty=0.15, requires_license=True)
    gross, net = compute_sales(state, _released(genre="rpg", theme="fairy_tale", avg=8.0), console)
    assert gross > 0
    # Net revenue = gross × (1 - 0.15) = 85% of gross.
    assert net == int(round(gross * 0.85))


def test_compute_sales_pc_no_royalty_full_revenue() -> None:
    """PC (requires_license=False) -> net == gross (no royalty cut)."""
    state = _state(fans=10_000)
    console = _console(cur_pop=1.0, royalty=0.0, requires_license=False)
    gross, net = compute_sales(state, _released(genre="rpg", theme="fairy_tale", avg=8.0), console)
    assert net == gross


def test_compute_sales_combo_multiplier_scales_gross() -> None:
    """A matching (genre, theme) combo (rpg + fairy_tale = 1.5) boosts gross."""
    state = _state(fans=1000)  # boosts magnitude to keep the 1.5× ratio visible
    console = _console(cur_pop=1.0, royalty=0.0, requires_license=False)
    neutral_gross, _ = compute_sales(
        state, _released(genre="rpg", theme="not_real", avg=9.0), console,
    )
    combo_gross, _ = compute_sales(
        state, _released(genre="rpg", theme="fairy_tale", avg=9.0), console,
    )
    assert combo_gross == int(round(neutral_gross * 1.5))


def test_compute_sales_fans_increase_gross_copies() -> None:
    """More fans → higher gross copies (per the (1 + fans*factor) term)."""
    console = _console(cur_pop=1.0, royalty=0.0, requires_license=False)
    project = _released(genre="rpg", theme="not_real", avg=8.0)
    low, _ = compute_sales(_state(fans=0), project, console)
    high, _ = compute_sales(_state(fans=10_000), project, console)
    assert high > low


# --- fans_gained_from_sales --------------------------------------------


def test_fans_gained_from_sales_scales_linearly() -> None:
    """fans_gained = copies × FANS_PER_COPY (currently 1.0 per copy)."""
    assert fans_gained_from_sales(0) == 0
    assert fans_gained_from_sales(100) == int(100 * FANS_PER_COPY)
    assert fans_gained_from_sales(1_000_000) == 1_000_000


def test_fans_per_copy_is_one() -> None:
    """Spec §2.6: fans_per_copy default = 1.0 (locked for Wave 3)."""
    assert FANS_PER_COPY == 1.0
