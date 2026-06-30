"""Tests for T32: Deterministic playthrough (seed=42 → BANKRUPTCY → FROZEN).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 686-697:

- Run a deterministic playthrough with seed=42 for up to ``MAX_TICKS`` ticks.
- Each tick: advance time, run product market, competitor AI, event chain,
  and check ``evaluate_endings`` from T15. On any ending, stop.
- Assert (a) BANKRUPTCY eventually triggers, (b) final ``state_hash`` matches
  the frozen literal ``EXPECTED_BANKRUPTCY_HASH``, (c) ending triggers at the
  frozen literal tick ``EXPECTED_END_TICK``, (d) ``ending_history`` has length
  1 with type ``BANKRUPTCY``.

Lock-in protocol (mandatory per plan line 689):
    - First implementation run captures both literals into this file.
    - Re-run the test 2 consecutive times — if both produce same values, freeze.
    - If not, document balance issue and FAIL.

Implementation contract:
- Uses ``engine.advance`` directly (no Textual App) to avoid UI overhead.
- Uses ``tick_products``, ``step_competitors``, ``evaluate_events`` per tick
  to fully simulate the game.
- All random flows go through ``engine._rng`` (the shared ``GameRNG``),
  preserving the determinism invariant.
- The test runs in a few seconds; the 10000-tick cap is the spec ceiling.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.ending import EndingType
from htop_tycoon.domain.state import state_hash
from htop_tycoon.engine.cash_flow import process_payroll, process_revenue
from htop_tycoon.engine.competitor_ai import step_competitors
from htop_tycoon.engine.ending import apply_ending, evaluate_endings
from htop_tycoon.engine.event_chain import evaluate_events, load_events_catalog
from htop_tycoon.engine.product_market import tick_products
from htop_tycoon.engine.startup import new_started_game
from htop_tycoon.engine.tick import TickEngine

# ---------------------------------------------------------------------------
# Frozen literal placeholders (lock-in protocol from plan line 689).
#
# First-run values: ``None`` means "uninitialized; the first playthrough run
# will print the actual hash + tick to stderr so they can be captured".
# After the lock-in protocol completes (2 consecutive runs producing the
# same values), these are frozen to the actual literal values.
#
# Update procedure:
#   1. Run the test once — values are printed to stderr.
#   2. Paste the printed values into the two constants below.
#   3. Re-run 2x more to confirm stability across runs.
# ---------------------------------------------------------------------------

# Frozen literals — re-tuned for v0.2.0 (Waves 7-9: regime + dept_focus + cash_flow).
# Lock-in protocol per plan T32/T46:
#   - 3 consecutive runs of seed=42, max_ticks=10000 produced identical
#     tick=54 and state_hash below.
#   - cash flow regime modifiers + comp_ai baseline shifts push bankruptcy
#     from the v0.1.0 tick-13 baseline to tick-54; the determinism
#     contract holds (byte-identical output across runs).
EXPECTED_END_TICK: int | None = 54
EXPECTED_BANKRUPTCY_HASH: str | None = (
    "0abd86f0c96f085066709e50422fd5b28cbc8408ffcbe1a870254e5d4313d379"
)

# Spec ceiling (plan line 689): 10000 ticks max. Do NOT increase without
# documenting the rationale in .omo/evidence/task-32-htop-tycoon.txt.
MAX_TICKS: int = 10_000

# Locked seed from the T32 spec.
SEED: int = 42

# Runtime budget: the playthrough must finish within 60 seconds on CI.
# If the test consistently exceeds this budget, the per-tick work is too
# expensive (e.g., product_market or events evaluate slowly) and should
# be profiled, not papered over with a longer timeout.
MAX_RUNTIME_SECONDS: float = 60.0


# ---------------------------------------------------------------------------
# Pure playthrough runner.
# ---------------------------------------------------------------------------


def _run_playthrough(seed: int, max_ticks: int) -> dict[str, object]:
    """Run a deterministic playthrough; return a diagnostics dict.

    The diagnostic fields are explicitly typed via the local variable
    assignments below so downstream consumers (``test_playthrough_*``) can
    index into the returned dict without mypy ``object``-subscript errors.

    The runner drives the engine directly:
        1. ``engine.advance(state, 1)`` — time + RNG tick.
        2. ``tick_products(state, engine._rng)`` — product lifecycle + share.
        3. ``step_competitors(state, engine._rng)`` — competitor AI.
        4. ``evaluate_events(...)`` — event chain evaluation.
        5. ``evaluate_endings(state, balance)`` — T15 dispatcher; stop on hit.

    Pure function over ``(seed, max_ticks)``: the same inputs yield the same
    outputs on every run, on every platform (this is the determinism
    invariant locked by ``test_tick_determinism.py``).

    Returns:
        A diagnostics dict with: ``tick``, ``hash``, ``ending``,
        ``cash_at_end``, ``competitor_actions``, ``events_fired``,
        ``game_time_week``, ``game_time_quarter``, ``game_time_year``.
    """
    state = new_started_game(seed)
    engine = TickEngine(seed)
    events_catalog = load_events_catalog()
    balance = load_balance()

    ending_observed: EndingType | None = None
    competitor_actions_count: int = 0
    events_fired_count: int = 0

    for _ in range(max_ticks):
        # (1) Time advance — TickEngine advances RNG once per tick.
        state = engine.advance(state, 1)

        # (2) Product market — share + revenue refresh.
        state = tick_products(state, engine._rng)

        # (3) Competitor AI — emits CompetitorAction events.
        state, comp_events = step_competitors(state, engine._rng)
        competitor_actions_count += len(comp_events)

        # (4) Event chain evaluation — fires random + conditional events.
        state, fired_events, _ = evaluate_events(state, engine._rng, balance, events_catalog, [])
        events_fired_count += len(fired_events)

        state = process_revenue(state, balance)
        state = process_payroll(state, balance)
        ending = evaluate_endings(state, balance)
        if ending is not None:
            state, _ = apply_ending(state, ending)
            ending_observed = ending
            break

    return {
        "tick": state.tick,
        "hash": state_hash(state),
        "ending": ending_observed,
        "cash_at_end": state.company.cash,
        "competitor_actions": competitor_actions_count,
        "events_fired": events_fired_count,
        "game_time_week": state.game_time.week,
        "game_time_quarter": state.game_time.quarter,
        "game_time_year": state.game_time.year,
        "ending_history_len": len(state.ending_history),
        "ending_history": list(state.ending_history),
    }


def _format_diagnostic(diag: dict[str, object]) -> str:
    """Return a single-line diagnostic string for stderr."""
    return (
        f"[T32 playthrough] seed={SEED} max_ticks={MAX_TICKS} "
        f"-> tick={diag['tick']} cash={diag['cash_at_end']} "
        f"ending={diag['ending']!r} "
        f"competitor_actions={diag['competitor_actions']} "
        f"events_fired={diag['events_fired']} "
        f"game_time=Y{diag['game_time_year']}Q{diag['game_time_quarter']}W{diag['game_time_week']} "
        f"state_hash={diag['hash']}"
    )


# ---------------------------------------------------------------------------
# Test class: deterministic playthrough reaches BANKRUPTCY.
# ---------------------------------------------------------------------------


class TestDeterministicPlaythrough:
    """seed=42 playthrough reaches BANKRUPTCY with frozen hash + tick."""

    def test_playthrough_seed_42_reaches_bankruptcy(self) -> None:
        """Given: seed=42, max 10000 ticks, all engine subsystems enabled
        When: the playthrough runs to completion or first ending
        Then: BANKRUPTCY triggers; final state_hash + tick match the
              frozen literals; ending_history has exactly 1 BANKRUPTCY marker.
        """
        diag = _run_playthrough(SEED, MAX_TICKS)
        # Print diagnostics for human review; pytest captures stdout/stderr
        # by default but ``-s`` makes it visible during development.
        print(_format_diagnostic(diag))

        # Assertion (a): BANKRUPTCY triggers deterministically.
        ending = diag["ending"]
        if ending != EndingType.BANKRUPTCY:
            pytest.fail(
                "BANKRUPTCY ending did NOT trigger within "
                f"{MAX_TICKS} ticks. This is a balance issue: the engine "
                "has no per-tick cash-deduction mechanism (no payroll, no "
                "weekly operating cost), so player cash stays at starting "
                "value (50000) and bankruptcy is unreachable. "
                f"Diagnostics: {_format_diagnostic(diag)} "
                "See .omo/evidence/task-32-htop-tycoon.txt for the full "
                "diagnostic dump and the failure rationale."
            )

        # Assertion (b): frozen hash literal.
        if EXPECTED_BANKRUPTCY_HASH is None:
            pytest.fail(
                "EXPECTED_BANKRUPTCY_HASH is None — run the test once to "
                "capture the actual hash from the printed diagnostic, then "
                "paste it into the literal. "
                f"Current actual hash: {diag['hash']!r}"
            )
        assert diag["hash"] == EXPECTED_BANKRUPTCY_HASH, (
            f"state_hash mismatch. actual={diag['hash']!r} expected={EXPECTED_BANKRUPTCY_HASH!r}"
        )

        # Assertion (c): frozen end_tick literal.
        if EXPECTED_END_TICK is None:
            pytest.fail(
                "EXPECTED_END_TICK is None — run the test once to capture "
                "the actual tick from the printed diagnostic, then paste it "
                f"into the literal. Current actual tick: {diag['tick']}"
            )
        assert diag["tick"] == EXPECTED_END_TICK, (
            f"end_tick mismatch. actual={diag['tick']} expected={EXPECTED_END_TICK}"
        )

        # Assertion (d): ending_history has exactly 1 BANKRUPTCY marker.
        assert diag["ending_history_len"] == 1, (
            f"ending_history must have length 1, got {diag['ending_history_len']} "
            f"(entries={diag['ending_history']!r})"
        )
        ending_history_raw = cast(list[Any], diag["ending_history"])
        marker = ending_history_raw[0]
        marker_type_name = type(marker).__name__
        assert isinstance(marker, dict), f"ending_history[0] must be dict, got {marker_type_name}"
        marker_kind = marker.get("kind")
        assert marker_kind == "ending_triggered", (
            f"ending_history[0].kind must be 'ending_triggered', got {marker_kind!r}"
        )
        marker_ending_type = marker.get("ending_type")
        assert marker_ending_type == "BANKRUPTCY", (
            f"ending_history[0].ending_type must be 'BANKRUPTCY', got {marker_ending_type!r}"
        )

    def test_playthrough_is_deterministic_across_runs(self) -> None:
        """Lock-in protocol: the same (seed, max_ticks) yields the same
        (end_tick, state_hash) on every run.

        This is the second-half of the lock-in protocol: run the playthrough
        N=3 times and assert all runs produce identical (tick, hash). If
        determinism is broken, this test fails before the literal assertions
        even get a chance to run.
        """
        diag_first = _run_playthrough(SEED, MAX_TICKS)
        print(_format_diagnostic(diag_first))
        for run_idx in range(2):
            diag_next = _run_playthrough(SEED, MAX_TICKS)
            assert diag_next["tick"] == diag_first["tick"], (
                f"run #{run_idx + 2}: tick differs. "
                f"first={diag_first['tick']} this={diag_next['tick']}"
            )
            assert diag_next["hash"] == diag_first["hash"], (
                f"run #{run_idx + 2}: state_hash differs. "
                f"first={diag_first['hash']} this={diag_next['hash']}"
            )
            assert diag_next["ending"] == diag_first["ending"], (
                f"run #{run_idx + 2}: ending differs. "
                f"first={diag_first['ending']!r} this={diag_next['ending']!r}"
            )

    def test_playthrough_runtime_under_budget(self) -> None:
        """Sanity: the full 10000-tick playthrough finishes within 60 seconds.

        Catches a class of regressions where the engine gets accidentally
        O(n^2) or worse — the test would time out and fail loudly instead of
        silently making CI crawl.
        """
        import time

        start = time.monotonic()
        _run_playthrough(SEED, MAX_TICKS)
        elapsed = time.monotonic() - start
        assert elapsed < MAX_RUNTIME_SECONDS, (
            f"playthrough took {elapsed:.1f}s, exceeds budget {MAX_RUNTIME_SECONDS}s"
        )
