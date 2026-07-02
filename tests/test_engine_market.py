"""htop-tycoon v3.0 — engine.market coverage tests. Spec §2.6, §2.8.

Targets ``engine/market.py`` (currently 44% covered) to push above 80%.

Verifies the two daily market updates driven by ``tick_market``:
1. Console lifecycle (linear ramp → peak → linear decline → snap to 0).
2. Fan decay every ``_TICKS_PER_QUARTER`` (90) game-days.
"""
from __future__ import annotations

import dataclasses

import pytest

from htop_tycoon.domain import (
    ConsoleId,
    ConsoleMarket,
    GameState,
    Market,
)
from htop_tycoon.engine.market import tick_market

# Spec §2.6 — mirrored from balance.yaml
_DAYS_PER_YEAR = 365
_TICKS_PER_QUARTER = 90
_FAN_DECAY_PCT = 0.02


# --- helpers --------------------------------------------------------------


def _console(
    *,
    cid: str = "c1",
    base_pop: float = 1.0,
    peak_year: int = 3,
    decline_rate: float = 0.1,
    disc_year: int | None = None,
    royalty: float = 0.15,
    requires_license: bool = True,
    day_since: int = 0,
    cur_pop: float | None = None,
) -> ConsoleMarket:
    """Build a ConsoleMarket for tests; cur_pop defaults to base_pop."""
    return ConsoleMarket(
        id=ConsoleId(cid),
        name_ko="테스트 콘솔",
        base_popularity=base_pop,
        release_year=1,
        peak_year=peak_year,
        decline_rate=decline_rate,
        discontinue_year=disc_year,
        royalty_rate=royalty,
        requires_license=requires_license,
        current_popularity=cur_pop if cur_pop is not None else base_pop,
        day_since_release=day_since,
    )


def _state_with(*consoles: ConsoleMarket, day: int = 0, fans: int = 0) -> GameState:
    """GameState containing only the given consoles (and optional day/fans)."""
    market = Market(consoles=consoles)
    return GameState(rng_seed=42, market=market, day=day, fans=fans)


# --- console lifecycle: day_since_release advances by 1 -----------------


def test_tick_market_advances_day_since_release_by_one() -> None:
    """Each tick increments every console's day_since_release by 1."""
    c = _console(day_since=10)
    state = _state_with(c, day=20)
    new_state, _ = tick_market(state)
    updated = new_state.market.consoles[0]
    assert updated.day_since_release == 11


def test_tick_market_no_events_for_alive_console() -> None:
    """A console with positive popularity emits no events."""
    c = _console(day_since=100, cur_pop=0.5)
    state = _state_with(c, day=100)
    _, events = tick_market(state)
    assert events == []


# --- console lifecycle: before peak (ramp up) ---------------------------


def test_tick_market_ramp_up_before_peak() -> None:
    """Before peak: popularity is a linear ramp from release to peak."""
    # day_since=0..peak_day-1 -> popularity = base * (day/peak_day)
    c = _console(base_pop=1.0, peak_year=3, day_since=0)  # peak_day = 1095
    state = _state_with(c, day=0)
    new_state, _ = tick_market(state)
    updated = new_state.market.consoles[0]
    # day_since advances to 1; popularity = 1.0 * (1/1095) ≈ 0.000913
    assert 0.0 <= updated.current_popularity < updated.base_popularity


def test_tick_market_at_peak_returns_full_popularity() -> None:
    """At exactly peak_day: popularity == base_popularity."""
    peak_day = 3 * _DAYS_PER_YEAR
    c = _console(base_pop=1.0, peak_year=3, day_since=peak_day - 1)
    state = _state_with(c, day=peak_day)
    new_state, _ = tick_market(state)
    updated = new_state.market.consoles[0]
    assert updated.current_popularity == pytest.approx(1.0, abs=1e-9)


# --- console lifecycle: after peak (decline) ----------------------------


def test_tick_market_declines_after_peak_no_discontinue() -> None:
    """After peak without discontinue_year: linear decline at decline_rate per year."""
    peak_day = 2 * _DAYS_PER_YEAR
    c = _console(
        base_pop=1.0,
        peak_year=2,
        decline_rate=0.5,
        disc_year=None,
        day_since=peak_day + 364,  # one tick → 1 year past peak
    )
    state = _state_with(c, day=peak_day + 364)
    new_state, _ = tick_market(state)
    # years_past_peak = 1 → popularity = 1.0 - 0.5 * 1 = 0.5
    assert new_state.market.consoles[0].current_popularity == pytest.approx(0.5, abs=1e-9)


# --- console lifecycle: snap to 0 at discontinue_year -------------------


def test_tick_market_snaps_to_zero_at_discontinue_year() -> None:
    """Reaching discontinue_year snaps popularity to 0 (licensed console)."""
    disc_year = 5
    c = _console(
        base_pop=1.0,
        peak_year=2,
        decline_rate=0.1,
        disc_year=disc_year,
        day_since=disc_year * _DAYS_PER_YEAR - 1,  # one day before
    )
    state = _state_with(c, day=disc_year * _DAYS_PER_YEAR)
    new_state, events = tick_market(state)
    updated = new_state.market.consoles[0]
    assert updated.current_popularity == 0.0
    assert updated.declined_at_day == state.day
    assert len(events) == 1
    assert events[0].kind == "console_discontinue"
    assert events[0].payload["console_id"] == c.id


def test_tick_market_does_not_emit_discontinue_event_twice() -> None:
    """An already-declined console does NOT re-emit the discontinue event."""
    c = _console(
        base_pop=1.0,
        peak_year=2,
        decline_rate=0.1,
        disc_year=5,
        day_since=5 * _DAYS_PER_YEAR - 1,
        cur_pop=0.0,
    )
    # Mark it as already declined before the tick:
    c = dataclasses.replace(c, declined_at_day=100)
    state = _state_with(c, day=200)
    _, events = tick_market(state)
    # The console hit 0 *again* but already had declined_at_day set, so no event.
    assert events == []


def test_tick_market_permanent_console_never_discontinued_event() -> None:
    """PC / OWN_CONSOLE (disc_year=None) never emit a discontinue event."""
    c = _console(
        base_pop=1.0,
        peak_year=2,
        decline_rate=10.0,  # extreme decline
        disc_year=None,
        day_since=2 * _DAYS_PER_YEAR,
        requires_license=False,
    )
    state = _state_with(c, day=2 * _DAYS_PER_YEAR)
    # Tick many years — popularity stays clamped at 0 (max with decline).
    for _ in range(10):
        state, events = tick_market(state)
        assert events == []
    # Declined_at_day is never set for permanent consoles.
    assert state.market.consoles[0].declined_at_day is None


# --- fan decay -----------------------------------------------------------


def test_tick_market_fan_decay_after_quarter() -> None:
    """After _TICKS_PER_QUARTER days, fans are reduced by _FAN_DECAY_PCT."""
    c = _console()  # irrelevant for fan decay path
    state = _state_with(c, day=_TICKS_PER_QUARTER, fans=1000)
    new_state, _ = tick_market(state)
    assert new_state.fans == int(1000 * (1.0 - _FAN_DECAY_PCT))
    # last_decay_day should be advanced to state.day
    assert new_state.market.last_decay_day == _TICKS_PER_QUARTER


def test_tick_market_no_decay_before_quarter() -> None:
    """Within the same quarter, fans are unchanged."""
    c = _console()
    state = _state_with(c, day=_TICKS_PER_QUARTER - 1, fans=1000)
    new_state, _ = tick_market(state)
    assert new_state.fans == 1000
    assert new_state.market.last_decay_day == 0


def test_tick_market_no_decay_when_fans_zero() -> None:
    """When fans == 0, decay is a no-op (no negative-clamp trap)."""
    c = _console()
    state = _state_with(c, day=_TICKS_PER_QUARTER, fans=0)
    new_state, _ = tick_market(state)
    assert new_state.fans == 0


def test_tick_market_last_decay_does_not_advance_when_fans_zero() -> None:
    """Spec §2.6: fan decay is gated on fans > 0; at fans=0 the cadence is skipped."""
    c = _console()
    state = _state_with(c, day=_TICKS_PER_QUARTER, fans=0)
    new_state, _ = tick_market(state)
    # Engine guard: `days_since_decay >= _TICKS_PER_QUARTER and state.fans > 0`.
    # When fans == 0, last_decay_day stays at its prior value.
    assert new_state.market.last_decay_day == 0
    assert new_state.fans == 0


# --- multiple consoles ---------------------------------------------------


def test_tick_market_processes_all_consoles() -> None:
    """All consoles in the market are advanced in one call."""
    c1 = _console(cid="c1", peak_year=3, day_since=10)
    c2 = _console(cid="c2", peak_year=4, day_since=20)
    state = _state_with(c1, c2, day=30)
    new_state, _ = tick_market(state)
    assert new_state.market.consoles[0].day_since_release == 11
    assert new_state.market.consoles[1].day_since_release == 21
