"""htop-tycoon v3.0 — market dynamics. Spec §2.6, §2.8.

Wave 3 engine: two daily market updates driven by :func:`tick_market`:

1. **Console lifecycle** (spec §2.8) — each ``ConsoleMarket`` advances one
   game-day along its popularity curve. Past ``peak_year``, popularity
   declines at ``decline_rate`` per year. At ``discontinue_year`` (if set),
   popularity drops to 0 and the console is marked discontinued via
   ``declined_at_day``. The engine emits a one-time
   ``"console_discontinue"`` event when a console first hits zero.

2. **Fan decay** (spec §2.6) — every ``ticks_per_quarter`` (90) game-days,
   the company's fan count is reduced by ``decay_per_quarter_pct`` (2 %).

NOTE on magic numbers (AGENTS.md §5.4 invariant): the constants below are
hardcoded for Wave 3 and mirror ``data/balance.yaml::time.days_per_year``,
``data/balance.yaml::time.ticks_per_quarter``, and
``data/balance.yaml::fans.decay_per_quarter_pct``. The Wave 4 data-loader
will replace these with proper YAML reads.
"""
from __future__ import annotations

import dataclasses

from htop_tycoon.domain import ConsoleMarket, Event, GameState

# Spec §2.6 — game-days per in-game year. balance.yaml::time.days_per_year.
_DAYS_PER_YEAR: int = 365

# Spec §2.6 — fan-decay cadence (game-days between decay ticks).
# balance.yaml::time.ticks_per_quarter.
_TICKS_PER_QUARTER: int = 90

# Spec §2.6 — fractional fan loss per decay tick.
# balance.yaml::fans.decay_per_quarter_pct.
_FAN_DECAY_PCT: float = 0.02


def tick_market(state: GameState) -> tuple[GameState, list[Event]]:
    """Advance market state by one game-day.

    Returns ``(new_state, events)`` — both may be empty/nil depending on
    whether any console hit zero or the fan-decay cadence elapsed.
    """
    new_consoles: list[ConsoleMarket] = []
    events: list[Event] = []

    # 1. Console lifecycle (spec §2.8).
    for cm in state.market.consoles:
        new_day_since = cm.day_since_release + 1
        new_popularity = _compute_popularity(cm, new_day_since)
        was_declined = cm.declined_at_day is not None
        hit_zero_now = new_popularity <= 0.0 and not was_declined
        new_declined_at_day = state.day if hit_zero_now else cm.declined_at_day
        if hit_zero_now:
            events.append(
                Event(
                    kind="console_discontinue",
                    day=state.day,
                    payload={"console_id": cm.id, "name_ko": cm.name_ko},
                )
            )
        new_consoles.append(
            dataclasses.replace(
                cm,
                day_since_release=new_day_since,
                current_popularity=new_popularity,
                declined_at_day=new_declined_at_day,
            )
        )

    # 2. Fan decay — every ``_TICKS_PER_QUARTER`` game-days (spec §2.6).
    days_since_decay = state.day - state.market.last_decay_day
    new_fans: int = state.fans
    new_last_decay_day: int = state.market.last_decay_day
    if days_since_decay >= _TICKS_PER_QUARTER and state.fans > 0:
        new_fans = int(state.fans * (1.0 - _FAN_DECAY_PCT))
        new_last_decay_day = state.day

    new_market = dataclasses.replace(
        state.market,
        consoles=tuple(new_consoles),
        last_decay_day=new_last_decay_day,
    )
    return state.replace(market=new_market, fans=new_fans), events


def _compute_popularity(cm: ConsoleMarket, day_since: int) -> float:
    """Apply the console-popularity curve (spec §2.8, Wave 3 simplified).

    Linear ramp up to ``peak_year * _DAYS_PER_YEAR``, then linear decline at
    ``decline_rate`` per year. If ``discontinue_year`` is set and reached,
    the curve snaps to 0. For ``PC`` and ``OWN_CONSOLE`` (``discontinue_year``
    is ``None``), popularity declines indefinitely toward 0 but never
    reaches it on its own — the engine will still mark ``declined_at_day``
    only when the curve crosses zero.

    The full S-curve / multiplicative model from spec §2.8 is Wave 4. This
    simplified version preserves the qualitative shape (rise → peak → fall)
    so the Wave 3 frozen-hash regression tests stay meaningful.
    """
    if day_since <= 0:
        return cm.base_popularity
    peak_day = cm.peak_year * _DAYS_PER_YEAR
    if peak_day <= 0:
        return cm.base_popularity
    if day_since < peak_day:
        # Linear ramp from release to peak (factor 0..1).
        return cm.base_popularity * (day_since / peak_day)
    # Past peak: linear decline. For licensed consoles, snap to 0 at
    # ``discontinue_year``; for permanent consoles (PC, OWN_CONSOLE), keep
    # declining toward (but never below) 0.
    if cm.discontinue_year is not None:
        disc_day = cm.discontinue_year * _DAYS_PER_YEAR
        if day_since >= disc_day:
            return 0.0
    years_past_peak = (day_since - peak_day) / _DAYS_PER_YEAR
    return max(0.0, cm.base_popularity - cm.decline_rate * years_past_peak)


__all__ = ["tick_market"]

