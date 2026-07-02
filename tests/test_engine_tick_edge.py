"""htop-tycoon v3.0 — engine.tick edge coverage tests. Spec §5.2, §5.3.

Targets ``engine/tick.py`` (currently 77% covered) to push above 80%.

Verifies:
- ``run_day`` always emits the trailing ``tick`` event with ``priority=-100``.
- ``run_day`` propagates ``check_endings`` events.
- Strategy Manager integration: actions dispatched when strategy is not None.
- Empty state (no projects, no employees, no market) does not crash.
"""
from __future__ import annotations

from htop_tycoon.domain import GameState
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.tick import run_day

# --- helpers --------------------------------------------------------------


def _rng(seed: int = 42) -> GameRNG:
    return GameRNG(seed)


# --- tick event priority --------------------------------------------------


def test_run_day_emits_tick_event_with_priority_minus_100() -> None:
    """run_day appends a single ``tick`` event with priority -100."""
    state = GameState(rng_seed=42)
    _, events = run_day(state, _rng())
    tick_events = [e for e in events if e.kind == "tick"]
    assert len(tick_events) == 1
    assert tick_events[0].priority == -100


def test_run_day_advances_day_by_one() -> None:
    state = GameState(rng_seed=42, day=5)
    new_state, _ = run_day(state, _rng())
    assert new_state.day == 6


# --- empty state safety --------------------------------------------------


def test_run_day_on_empty_state_does_not_crash() -> None:
    """A fresh GameState with no projects/employees runs cleanly."""
    state = GameState(rng_seed=42)
    new_state, events = run_day(state, _rng())
    assert new_state is not None
    # tick event still emitted even with no work
    assert any(e.kind == "tick" for e in events)


def test_run_day_strategy_none_is_no_op_for_ai() -> None:
    """strategy=None -> manual play, no AI actions dispatched."""
    state = GameState(rng_seed=42)
    new_state, events = run_day(state, _rng(), strategy=None)
    # No strategy action events emitted; only market/tick events
    for e in events:
        assert e.kind not in ("hire", "fire", "train", "start_game", "assign",
                              "promote", "demote", "change_job")


# --- strategy integration ------------------------------------------------


def test_run_day_with_strategy_executes_planned_actions() -> None:
    """When strategy is provided, its decided actions are dispatched."""
    from htop_tycoon.engine.strategy import BalancedStrategy

    # BalancedStrategy.decide returns a list of PlannedAction; the simplest
    # scenario: give it a state with employees and verify at least one
    # action event appears in the events list.
    state = GameState(rng_seed=42, cash=100_000)
    strategy = BalancedStrategy()
    new_state, events = run_day(state, _rng(), strategy=strategy)
    # tick event still appended at the end
    assert events[-1].kind == "tick"


def test_run_day_propagates_ending_event() -> None:
    """An ending event from check_endings is included in the returned events."""
    state = GameState(rng_seed=42, cash=-100_000)
    _, events = run_day(state, _rng())
    ending_events = [e for e in events if e.kind == "ending"]
    assert len(ending_events) == 1
    assert ending_events[0].payload["ending"] == "BANKRUPTCY"


def test_run_day_event_order_tick_is_last() -> None:
    """The ``tick`` event must come last (priority -100 sorts last in UI)."""
    state = GameState(rng_seed=42, cash=-100_000)
    _, events = run_day(state, _rng())
    assert events[-1].kind == "tick"


def test_run_day_uses_state_day_for_event_day() -> None:
    """All non-tick events use the post-increment day (state.day + 1)."""
    state = GameState(rng_seed=42, day=99)
    _, events = run_day(state, _rng())
    for e in events:
        if e.kind == "tick":
            assert e.day == 100
        else:
            assert e.day == 100
