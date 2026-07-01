"""htop-tycoon v3.0 — sales formula + combo lookup. Spec §2.2 step 8, §2.6, §2.7.

Wave 3 follow-up: ``engine/sales.py`` was deferred from the main Wave 3
commit because the formula needs careful integration with
``data/combos.yaml`` (15 entries) and ``data/balance.yaml`` (sales
constants). This module lands it as a focused, reviewable follow-up.

Spec §2.2 step 8: ``sales_revenue = (quality_avg / 10) × platform_popularity
× (1 + fans × base_fan_factor)``. Combo bonuses from §2.7 multiply the
copies count. Royalty per spec §2.3: 15 percent for licensed consoles
(PC and OWN_CONSOLE are royalty-free).

Combo multipliers are hardcoded from ``data/combos.yaml`` (Wave 5+
data loader will source from the YAML at runtime). Default multiplier is
1.0 for non-matching (genre, theme) pairs.
"""
from __future__ import annotations

from htop_tycoon.domain import ConsoleMarket, GameProject, GameState

# Spec §2.6 — balance constants; mirror ``data/balance.yaml::sales.{...}``.
_QUALITY_AVG_DIVISOR: float = 10.0
_POPULARITY_WEIGHT: float = 1.0
_FAN_FACTOR_WEIGHT: float = 1.0
_BASE_FAN_FAN_FACTOR: float = 0.001
_ROYALTY_LICENSED: float = 0.15
_ROYALTY_OWN: float = 0.0
_PER_SALE_FACTOR: float = 1.0  # spec §2.6 fans-per-copy factor

# Spec §2.7 — combo multipliers. Hardcoded from ``data/combos.yaml``
# (15 entries). Key is ``(genre_id, theme_id)``; value is the multiplier.
# Default (no match) returns 1.0. Wave 5+ will source from the YAML.
_COMBO_MULTIPLIERS: dict[tuple[str, str], float] = {
    ("action", "stealth"): 2.0,         # spec §2.7 — 닌자 액션
    ("rhythm", "music"): 1.5,          # spec §2.7 — 댄스 리듬
    ("rpg", "fairy_tale"): 1.5,        # spec §2.7 — 송이버섯 RPG
    ("simulation", "modern"): 1.3,     # spec §2.7 — 편의점 시뮬
    ("rpg", "time_travel"): 1.6,
    ("action", "zombie"): 1.7,
    ("strategy", "martial_arts"): 1.4,
    ("horror", "yokai"): 1.8,
    ("sports", "sports"): 1.3,
    ("adventure", "pirate"): 1.5,
    ("puzzle", "magic"): 1.4,
    ("fighting", "samurai"): 1.6,
    ("educational", "animal"): 1.3,
    ("action", "space"): 1.4,
    ("rpg", "magic"): 1.2,
}

# Spec §2.6 — fans per copy sold.
FANS_PER_COPY: float = _PER_SALE_FACTOR

# Spec §2.3 — default royalty fallback when ``ConsoleMarket.royalty_rate``
# is unavailable. PC and OWN_CONSOLE always pay 0.
_DEFAULT_ROYALTY: float = _ROYALTY_LICENSED


def get_combo_multiplier(genre_id: str, theme_id: str) -> float:
    """Return the sales multiplier for a ``(genre, theme)`` pair per spec §2.7.

    Returns 1.0 for non-matching pairs (neutral; no bonus or penalty).
    """
    return _COMBO_MULTIPLIERS.get((genre_id, theme_id), 1.0)


def _resolve_royalty(console: ConsoleMarket) -> float:
    """Spec §2.3: PC and OWN_CONSOLE pay 0; licensed consoles pay 15 percent."""
    if console.requires_license:
        return console.royalty_rate if console.royalty_rate > 0 else _DEFAULT_ROYALTY
    return _ROYALTY_OWN


def compute_sales(
    state: GameState,
    project: GameProject,
    console: ConsoleMarket,
) -> tuple[int, int]:
    """Spec §2.2 step 8 + §2.6 + §2.7.

    Computes one tick of sales for ``project`` on ``console`` given the
    current ``state`` (for ``state.fans`` and platform popularity).

    Returns ``(gross_copies, net_revenue_after_royalty)``:
      - ``gross_copies`` = max(0, round(
            (quality_avg / 10) × platform_popularity
            × (1 + fans × base_fan_factor)
            × combo_multiplier
        ))
      - ``net_revenue_after_royalty`` = gross_copies × (1 - royalty_rate)

    The first arg ``state`` is used to read ``state.fans`` and
    ``console.current_popularity``; pass the live game state. The function
    is pure given fixed inputs.

    Returns ``(0, 0)`` for unreleased / never-released projects.
    """
    if not project.is_released or project.current_quality_avg <= 0.0:
        return (0, 0)
    if console.current_popularity <= 0.0:
        return (0, 0)

    quality = project.current_quality_avg
    popularity = console.current_popularity
    fans = state.fans
    combo = get_combo_multiplier(project.genre_id, project.theme_id)

    raw = (
        (quality / _QUALITY_AVG_DIVISOR)
        * (popularity * _POPULARITY_WEIGHT)
        * (1.0 + fans * _FAN_FACTOR_WEIGHT * _BASE_FAN_FAN_FACTOR)
        * combo
    )
    gross_copies = max(0, int(round(raw)))
    royalty_rate = _resolve_royalty(console)
    net_revenue = int(round(gross_copies * (1.0 - royalty_rate)))
    return (gross_copies, net_revenue)


def fans_gained_from_sales(gross_copies: int) -> int:
    """Spec §2.6: ``fans += copies_sold × per_sale_factor``."""
    return int(gross_copies * FANS_PER_COPY)


__all__ = [
    "FANS_PER_COPY",
    "compute_sales",
    "fans_gained_from_sales",
    "get_combo_multiplier",
]
