"""Tests for T33: 5 endings reachable + seed fixtures in seeds.yaml.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 701-720:

- 5 separate tests, one per ``EndingType`` (BANKRUPTCY, IPO, HOSTILE_MA,
  VOLUNTARY_SALE, SECRET).
- Each test loads its fixture from ``src/htop_tycoon/data/seeds.yaml``,
  constructs (or drives) a GameState that triggers the ending, runs the
  full engine pipeline
  (TickEngine.advance + tick_products + step_competitors + evaluate_events +
  process_revenue + process_payroll + evaluate_endings + apply_ending),
  and asserts:
    (a) the ending triggers,
    (b) the correct EndingType is in ``state.ending_history``,
    (c) the final ``state_hash`` matches the frozen literal for that ending.
- Per-ending fixture metadata: ``seed``, ``expected_tick``, ``command_line``.
- SECRET is included (the test constructs the state directly; the engine
  cannot reach SECRET in reasonable ticks without complex setup).
- No brute-force search for seeds at runtime; fixtures are precomputed
  in this test file's frozen literals (lock-in protocol per T32).

The hashes are frozen via the lock-in protocol:
    1. First run captures actual hashes from diagnostics printed to stdout.
    2. Paste the printed values into the EXPECTED_*_HASH literals below.
    3. Re-run 2 consecutive times to confirm stability across runs.

BANKRUPTCY uses the natural playthrough pattern (seed=42 → tick 13); the
hash matches the T32 lock-in value (proves the per-tick cash flow added
in Wave 6 is consistent across tests).

The other 4 endings use a crafted-state pattern: build a GameState that
already satisfies the ending condition, run ``expected_tick`` ticks of
the full pipeline, then evaluate_endings + apply_ending, and verify the
hash. The pipeline does not modify the fields each crafted state holds
deliberately (market_cap, competitor cash/aggression/alive, dept.unlocked,
emp.skill, secret_investor_cleared), so the ending remains triggered after
the run and the resulting hash is deterministic.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, cast

import pytest

from htop_tycoon.data import load_balance, load_seeds
from htop_tycoon.domain.dept import Department, DepartmentType
from htop_tycoon.domain.employee import Employee
from htop_tycoon.domain.ending import EndingType
from htop_tycoon.domain.market import Competitor
from htop_tycoon.domain.state import (
    Company,
    DepartmentId,
    EmployeeId,
    GameState,
    state_hash,
)
from htop_tycoon.engine.cash_flow import process_payroll, process_revenue
from htop_tycoon.engine.competitor_ai import step_competitors
from htop_tycoon.engine.ending import apply_ending, evaluate_endings
from htop_tycoon.engine.event_chain import evaluate_events, load_events_catalog
from htop_tycoon.engine.product_market import tick_products
from htop_tycoon.engine.startup import new_started_game
from htop_tycoon.engine.tick import TickEngine

# ---------------------------------------------------------------------------
# Frozen literal placeholders (lock-in protocol from plan line 689 + 711).
#
# First-run values are ``None`` — they print actual hashes/ticks to stdout
# so the operator can capture and paste them. After 2 consecutive identical
# runs, the literals are frozen and the test becomes GREEN.
#
# Update procedure:
#   1. Run the test file once (RED → captures actual values).
#   2. Paste the printed values into the matching ``EXPECTED_*`` constants.
#   3. Re-run 2x more to confirm stability.
# ---------------------------------------------------------------------------

EXPECTED_BANKRUPTCY_TICK: int | None = 13
EXPECTED_BANKRUPTCY_HASH: str | None = (
    "71c22a2d345b05cb470387939d89b4090765e7778a4ae80e40fae5edf78a0a11"
)

EXPECTED_IPO_TICK: int | None = 1
EXPECTED_IPO_HASH: str | None = (
    "683e66651719b998d3a5964e71e1e6536d808e280928fd7c244cf125cbbca7d1"
)

EXPECTED_HOSTILE_MA_TICK: int | None = 1
EXPECTED_HOSTILE_MA_HASH: str | None = (
    "66e8af210fba4bfabefb347aa0784dd8097314828946ed5583f3699463bd2d10"
)

EXPECTED_VOLUNTARY_SALE_TICK: int | None = 1
EXPECTED_VOLUNTARY_SALE_HASH: str | None = (
    "532001969d869ecc49c796642e6dc1110bb7f2f149080314dcf8956f37a557dd"
)

EXPECTED_SECRET_TICK: int | None = 1
EXPECTED_SECRET_HASH: str | None = (
    "69f68540989f6cdcddc1c5d68fd44f5417eb488c8f72ca8b32e23714944a7caa"
)

# Seeds used for the fixtures and the BANKRUPTCY playthrough.
SEED_BANKRUPTCY: int = 42
SEED_IPO: int = 137
SEED_HOSTILE_MA: int = 256
SEED_VOLUNTARY_SALE: int = 512
SEED_SECRET: int = 1024

# Runtime budget: any single ending test must finish within 30 seconds.
MAX_RUNTIME_SECONDS: float = 30.0


# ---------------------------------------------------------------------------
# Shared seed-fixture loader.
# ---------------------------------------------------------------------------

_SEEDS_PATH: Path = (
    Path(__file__).resolve().parent.parent / "src" / "htop_tycoon" / "data" / "seeds.yaml"
)


# ---------------------------------------------------------------------------
# Pure helper: run a deterministic playthrough (same pattern as T32).
# ---------------------------------------------------------------------------


def _run_playthrough(seed: int, max_ticks: int) -> dict[str, Any]:
    """Run a deterministic playthrough; return a diagnostics dict.

    Mirrors ``tests/test_playthrough.py::_run_playthrough``: drives the engine
    directly per tick. Returns tick/hash/ending markers after the first
    ending triggers (or ``max_ticks`` if no ending fires).
    """
    state = new_started_game(seed)
    engine = TickEngine(seed)
    events_catalog = load_events_catalog()
    balance = load_balance()

    ending_observed: EndingType | None = None
    competitor_actions_count: int = 0
    events_fired_count: int = 0

    for _ in range(max_ticks):
        state = engine.advance(state, 1)
        state = tick_products(state, engine._rng)
        state, comp_events = step_competitors(state, engine._rng)
        competitor_actions_count += len(comp_events)
        state, fired_events, _ = evaluate_events(
            state, engine._rng, balance, events_catalog, []
        )
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
        "ending_history_len": len(state.ending_history),
        "ending_history": list(state.ending_history),
    }


# ---------------------------------------------------------------------------
# Pure helper: run ``n_ticks`` of the full engine pipeline on a crafted state.
# ---------------------------------------------------------------------------


def _drive_crafted_state(
    state: GameState, seed: int, n_ticks: int
) -> dict[str, Any]:
    """Drive a manually-constructed GameState through ``n_ticks`` of pipeline steps.

    The pipeline (per the project's T33 spec) is:
        1. TickEngine.advance(state, 1)
        2. tick_products(state, rng)
        3. step_competitors(state, rng)  -> (state, comp_events)
        4. evaluate_events(state, rng, balance, catalog, []) -> (state, fired, [])
        5. process_revenue(state, balance)
        6. process_payroll(state, balance)
        7. evaluate_endings(state, balance) — returns EndingType | None

    Args:
        state: The starting GameState. Not mutated.
        seed: RNG seed (for the TickEngine's RNG, shared with all per-tick consumers).
        n_ticks: How many ticks to drive.

    Returns:
        Diagnostics dict with ``state`` (the final state), ``hash``,
        ``ending``, ``ending_history``, and per-tick counters.
    """
    engine = TickEngine(seed)
    events_catalog = load_events_catalog()
    balance = load_balance()

    competitor_actions_count: int = 0
    events_fired_count: int = 0

    current = state
    for _ in range(n_ticks):
        current = engine.advance(current, 1)
        current = tick_products(current, engine._rng)
        current, comp_events = step_competitors(current, engine._rng)
        competitor_actions_count += len(comp_events)
        current, fired_events, _ = evaluate_events(
            current, engine._rng, balance, events_catalog, []
        )
        events_fired_count += len(fired_events)
        current = process_revenue(current, balance)
        current = process_payroll(current, balance)

    ending = evaluate_endings(current, balance, player_action=None)
    return {
        "state": current,
        "hash": state_hash(current),
        "ending_pre_apply": ending,
        "competitor_actions": competitor_actions_count,
        "events_fired": events_fired_count,
    }


# ---------------------------------------------------------------------------
# Pure helpers: build crafted GameState for each non-bankruptcy ending.
# ---------------------------------------------------------------------------


def _build_ipo_state() -> GameState:
    """State with market_cap >= IPO threshold and cash > 0 (BANKRUPTCY/HOSTILE_MA absent).

    Cash is set high enough (10_000) that per-tick payroll (5_000/week) and
    weekly revenue (~25/week) leave it positive after 1 tick of the pipeline.
    """
    base = new_started_game(SEED_IPO)
    balance = load_balance()
    ipo_threshold = int(balance["endings"]["ipo_market_cap_threshold"])
    new_company = Company(
        id="company-1", name="My Company", cash=10_000, market_cap=ipo_threshold * 3 // 2
    )
    return dataclasses.replace(base, company=new_company)


def _build_hostile_ma_state() -> GameState:
    """State with an alive competitor cash>=market_cap AND aggression > threshold.

    Player market_cap is set high enough that no IPO is triggered (but
    the competitor's cash is even higher). Player cash is non-negative
    (no BANKRUPTCY). The competitor has cash >= player market_cap and
    aggression strictly above the threshold.
    """
    base = new_started_game(SEED_HOSTILE_MA)
    balance = load_balance()
    ma_threshold = float(balance["endings"]["hostile_ma_trigger_competitor_aggression"])
    new_company = Company(
        id="company-1", name="My Company", cash=10_000, market_cap=1_000_000
    )
    competitor = Competitor(
        id="comp-raider",
        name="Raider-Co",
        market_share=0.0,
        aggression=ma_threshold + 0.1,  # strictly above threshold
        cash=2_000_000,  # >= market_cap (1_000_000)
        alive=True,
    )
    return dataclasses.replace(
        base,
        company=new_company,
        competitors={competitor.id: competitor},
    )


def _build_voluntary_sale_state() -> GameState:
    """State with cash >= voluntary_sale_min_cash (so VOLUNTARY_SALE can fire)."""
    base = new_started_game(SEED_VOLUNTARY_SALE)
    balance = load_balance()
    min_cash = int(balance["endings"]["voluntary_sale_min_cash"])
    new_company = Company(
        id="company-1", name="My Company", cash=min_cash + 100_000, market_cap=min_cash + 100_000
    )
    return dataclasses.replace(base, company=new_company)


def _build_secret_state() -> GameState:
    """State with 5 unlocked depts + all employees at max_skill + secret_investor_cleared.

    Each of the 3 SECRET sub-conditions is set:
      1. all departments unlocked (5 depts, one per DepartmentType)
      2. all employees at max_skill (=10)
      3. secret_investor_cleared=True
    """
    base = new_started_game(SEED_SECRET)
    balance = load_balance()
    max_skill = int(balance["employees"]["max_skill"])
    salary = int(balance["employees"]["starting_salary_per_week"])

    # 5 departments, one per DepartmentType, each with 1 employee at max_skill.
    dept_types = (
        DepartmentType.Engineering,
        DepartmentType.Sales,
        DepartmentType.Operations,
        DepartmentType.Marketing,
        DepartmentType.Finance,
    )
    departments: dict[DepartmentId, Department] = {}
    employees: dict[EmployeeId, Employee] = {}
    for i, dtype in enumerate(dept_types, start=1):
        did = DepartmentId(f"dept-{dtype.value.lower()}")
        eid = EmployeeId(f"emp-{dtype.value.lower()}")
        employees[eid] = Employee(
            id=eid,
            name=f"SecretEmployee{i}",
            dept_id=did,
            skill=max_skill,
            tier=1,
            salary_per_week=salary,
            satisfaction=70,
            hired_tick=0,
        )
        departments[did] = Department(
            id=did,
            type=dtype,
            head_employee_id=eid,
            employee_ids=[eid],
            founded_tick=0,
            unlocked=True,
        )

    return dataclasses.replace(
        base,
        departments=departments,
        employees=employees,
        secret_investor_cleared=True,
    )


# ---------------------------------------------------------------------------
# seeds.yaml fixture loader + accessor.
# ---------------------------------------------------------------------------


def _load_seeds_fixture() -> dict[str, dict[str, Any]]:
    """Load seeds.yaml and return the ``endings`` mapping."""
    seeds = load_seeds()
    if "endings" not in seeds:
        pytest.fail(
            f"seeds.yaml missing 'endings' top-level key: path={_SEEDS_PATH}"
        )
    endings = seeds["endings"]
    if not isinstance(endings, dict):
        pytest.fail(
            f"seeds.yaml 'endings' must be a mapping, got {type(endings).__name__}"
        )
    return cast(dict[str, dict[str, Any]], endings)


# ===========================================================================
# Test class: each of 5 endings is reachable.
# ===========================================================================


class TestAllFiveEndingsReachable:
    """Each EndingType must be reachable from a deterministic playthrough or
    a manually crafted state. Fixtures live in ``seeds.yaml`` and the
    per-ending expected hashes live as frozen literals in this file.
    """

    def test_bankruptcy_reachable_via_seed_42_playthrough(self) -> None:
        """Seed=42 playthrough reaches BANKRUPTCY at the frozen tick + hash.

        Given: seed=42, MAX_TICKS budget, full engine pipeline (advance +
               products + competitors + events + revenue + payroll +
               evaluate_endings + apply_ending)
        When:  the playthrough runs to first-ending or budget
        Then:  BANKRUPTCY triggers; state_hash matches frozen literal;
               tick matches frozen literal; ending_history has exactly 1
               BANKRUPTCY marker.
        """
        diag = _run_playthrough(SEED_BANKRUPTCY, max_ticks=10_000)
        print(
            f"[T33 BANKRUPTCY] seed={SEED_BANKRUPTCY} "
            f"-> tick={diag['tick']} cash={diag['cash_at_end']} "
            f"ending={diag['ending']!r} "
            f"state_hash={diag['hash']}"
        )

        assert diag["ending"] is EndingType.BANKRUPTCY, (
            f"BANKRUPTCY did not trigger within 10000 ticks. Diag={diag}"
        )

        if EXPECTED_BANKRUPTCY_HASH is None:
            pytest.fail(
                "EXPECTED_BANKRUPTCY_HASH is None — run once to capture the "
                f"actual hash. Current actual hash: {diag['hash']!r}"
            )
        assert diag["hash"] == EXPECTED_BANKRUPTCY_HASH, (
            f"hash mismatch. actual={diag['hash']!r} "
            f"expected={EXPECTED_BANKRUPTCY_HASH!r}"
        )

        if EXPECTED_BANKRUPTCY_TICK is None:
            pytest.fail(
                "EXPECTED_BANKRUPTCY_TICK is None — run once to capture the "
                f"actual tick. Current actual tick: {diag['tick']}"
            )
        assert diag["tick"] == EXPECTED_BANKRUPTCY_TICK, (
            f"tick mismatch. actual={diag['tick']} "
            f"expected={EXPECTED_BANKRUPTCY_TICK}"
        )

        # ending_history has exactly 1 BANKRUPTCY marker.
        assert diag["ending_history_len"] == 1
        marker = cast(dict[str, Any], diag["ending_history"][0])
        assert marker.get("kind") == "ending_triggered"
        assert marker.get("ending_type") == "BANKRUPTCY"

    def test_ipo_reachable_with_crafted_high_market_cap_state(self) -> None:
        """A state with market_cap >= ipo threshold + cash > 0 triggers IPO.

        Given: state with market_cap=ipo_threshold*1.5 and cash=1000
        When:  drive ``expected_tick`` ticks through the full pipeline
               then evaluate_endings + apply_ending
        Then:  IPO triggers; state_hash matches frozen literal;
               ending_history has exactly 1 IPO marker.
        """
        seeds_fixture = _load_seeds_fixture()
        assert "IPO" in seeds_fixture, "seeds.yaml must contain IPO fixture"
        ipo_seed = int(seeds_fixture["IPO"]["seed"])
        ipo_tick = int(seeds_fixture["IPO"]["expected_tick"])

        state = _build_ipo_state()
        diag = _drive_crafted_state(state, seed=ipo_seed, n_ticks=ipo_tick)
        assert diag["ending_pre_apply"] is EndingType.IPO, (
            f"IPO did not trigger after {ipo_tick} ticks. Diag={diag}"
        )

        # Apply IPO and freeze the post-apply hash.
        new_state, _ = apply_ending(diag["state"], EndingType.IPO)
        final_hash = state_hash(new_state)
        print(
            f"[T33 IPO] seed={ipo_seed} expected_tick={ipo_tick} "
            f"-> state_hash={final_hash}"
        )

        if EXPECTED_IPO_HASH is None:
            pytest.fail(
                "EXPECTED_IPO_HASH is None — run once to capture the actual "
                f"hash. Current actual hash: {final_hash!r}"
            )
        assert final_hash == EXPECTED_IPO_HASH, (
            f"hash mismatch. actual={final_hash!r} "
            f"expected={EXPECTED_IPO_HASH!r}"
        )

        if EXPECTED_IPO_TICK is None:
            pytest.fail(
                "EXPECTED_IPO_TICK is None — run once to capture the actual "
                "tick. Default expected_tick=1 from fixture."
            )
        assert ipo_tick == EXPECTED_IPO_TICK, (
            f"tick mismatch. fixture={ipo_tick} expected={EXPECTED_IPO_TICK}"
        )

        # ending_history has exactly 1 IPO marker (after apply_ending).
        assert len(new_state.ending_history) == 1
        marker = cast(dict[str, Any], new_state.ending_history[0])
        assert marker.get("kind") == "ending_triggered"
        assert marker.get("ending_type") == "IPO"

    def test_hostile_ma_reachable_with_crafted_competitor_state(self) -> None:
        """An alive competitor with cash >= market_cap + aggression>threshold triggers HOSTILE_MA.

        Given: state with one competitor cash=2_000_000, aggression=1.0,
               alive=True, and player market_cap=1_000_000
        When:  drive ``expected_tick`` ticks through the full pipeline
               then evaluate_endings + apply_ending
        Then:  HOSTILE_MA triggers; state_hash matches frozen literal;
               ending_history has exactly 1 HOSTILE_MA marker.
        """
        seeds_fixture = _load_seeds_fixture()
        assert "HOSTILE_MA" in seeds_fixture
        ma_seed = int(seeds_fixture["HOSTILE_MA"]["seed"])
        ma_tick = int(seeds_fixture["HOSTILE_MA"]["expected_tick"])

        state = _build_hostile_ma_state()
        diag = _drive_crafted_state(state, seed=ma_seed, n_ticks=ma_tick)
        assert diag["ending_pre_apply"] is EndingType.HOSTILE_MA, (
            f"HOSTILE_MA did not trigger after {ma_tick} ticks. Diag={diag}"
        )

        new_state, _ = apply_ending(diag["state"], EndingType.HOSTILE_MA)
        final_hash = state_hash(new_state)
        print(
            f"[T33 HOSTILE_MA] seed={ma_seed} expected_tick={ma_tick} "
            f"-> state_hash={final_hash}"
        )

        if EXPECTED_HOSTILE_MA_HASH is None:
            pytest.fail(
                "EXPECTED_HOSTILE_MA_HASH is None — run once to capture the "
                f"actual hash. Current actual hash: {final_hash!r}"
            )
        assert final_hash == EXPECTED_HOSTILE_MA_HASH, (
            f"hash mismatch. actual={final_hash!r} "
            f"expected={EXPECTED_HOSTILE_MA_HASH!r}"
        )

        if EXPECTED_HOSTILE_MA_TICK is None:
            pytest.fail(
                "EXPECTED_HOSTILE_MA_TICK is None — run once to capture the "
                "actual tick."
            )
        assert ma_tick == EXPECTED_HOSTILE_MA_TICK

        assert len(new_state.ending_history) == 1
        marker = cast(dict[str, Any], new_state.ending_history[0])
        assert marker.get("kind") == "ending_triggered"
        assert marker.get("ending_type") == "HOSTILE_MA"

    def test_voluntary_sale_reachable_with_sell_action(self) -> None:
        """Cash >= voluntary_sale_min + player_action='sell' triggers VOLUNTARY_SALE.

        Given: state with cash=min+100_000
        When:  drive ``expected_tick`` ticks, then evaluate_endings with
               player_action='sell'
        Then:  VOLUNTARY_SALE triggers; state_hash matches frozen literal;
               ending_history has exactly 1 VOLUNTARY_SALE marker.

        The crafted-state pattern (run 1 tick first then evaluate with the
        sell action) demonstrates that the engine pipeline does not break
        the VOLUNTARY_SALE condition during normal operation.
        """
        seeds_fixture = _load_seeds_fixture()
        assert "VOLUNTARY_SALE" in seeds_fixture
        vs_seed = int(seeds_fixture["VOLUNTARY_SALE"]["seed"])
        vs_tick = int(seeds_fixture["VOLUNTARY_SALE"]["expected_tick"])

        state = _build_voluntary_sale_state()
        diag = _drive_crafted_state(state, seed=vs_seed, n_ticks=vs_tick)
        balance = load_balance()
        ending = evaluate_endings(diag["state"], balance, player_action="sell")
        assert ending is EndingType.VOLUNTARY_SALE, (
            f"VOLUNTARY_SALE did not trigger with player_action='sell'. Diag={diag}"
        )

        new_state, _ = apply_ending(diag["state"], EndingType.VOLUNTARY_SALE)
        final_hash = state_hash(new_state)
        print(
            f"[T33 VOLUNTARY_SALE] seed={vs_seed} expected_tick={vs_tick} "
            f"-> state_hash={final_hash}"
        )

        if EXPECTED_VOLUNTARY_SALE_HASH is None:
            pytest.fail(
                "EXPECTED_VOLUNTARY_SALE_HASH is None — run once to capture "
                f"the actual hash. Current actual hash: {final_hash!r}"
            )
        assert final_hash == EXPECTED_VOLUNTARY_SALE_HASH, (
            f"hash mismatch. actual={final_hash!r} "
            f"expected={EXPECTED_VOLUNTARY_SALE_HASH!r}"
        )

        if EXPECTED_VOLUNTARY_SALE_TICK is None:
            pytest.fail(
                "EXPECTED_VOLUNTARY_SALE_TICK is None — run once to capture."
            )
        assert vs_tick == EXPECTED_VOLUNTARY_SALE_TICK

        assert len(new_state.ending_history) == 1
        marker = cast(dict[str, Any], new_state.ending_history[0])
        assert marker.get("kind") == "ending_triggered"
        assert marker.get("ending_type") == "VOLUNTARY_SALE"

    def test_secret_reachable_with_all_three_subconditions(self) -> None:
        """All 3 SECRET sub-conditions met -> SECRET triggers.

        Sub-conditions:
          1. all departments unlocked (5 depts in crafted state)
          2. all employees at max_skill (=10)
          3. secret_investor_cleared=True
        """
        seeds_fixture = _load_seeds_fixture()
        assert "SECRET" in seeds_fixture
        secret_seed = int(seeds_fixture["SECRET"]["seed"])
        secret_tick = int(seeds_fixture["SECRET"]["expected_tick"])

        state = _build_secret_state()

        # Verify all 3 sub-conditions before driving.
        balance = load_balance()
        max_skill = int(balance["employees"]["max_skill"])
        assert all(d.unlocked for d in state.departments.values())
        assert all(e.skill == max_skill for e in state.employees.values())
        assert state.secret_investor_cleared is True

        diag = _drive_crafted_state(state, seed=secret_seed, n_ticks=secret_tick)
        assert diag["ending_pre_apply"] is EndingType.SECRET, (
            f"SECRET did not trigger after {secret_tick} ticks. Diag={diag}"
        )

        new_state, _ = apply_ending(diag["state"], EndingType.SECRET)
        final_hash = state_hash(new_state)
        print(
            f"[T33 SECRET] seed={secret_seed} expected_tick={secret_tick} "
            f"-> state_hash={final_hash}"
        )

        if EXPECTED_SECRET_HASH is None:
            pytest.fail(
                "EXPECTED_SECRET_HASH is None — run once to capture the "
                f"actual hash. Current actual hash: {final_hash!r}"
            )
        assert final_hash == EXPECTED_SECRET_HASH, (
            f"hash mismatch. actual={final_hash!r} "
            f"expected={EXPECTED_SECRET_HASH!r}"
        )

        if EXPECTED_SECRET_TICK is None:
            pytest.fail(
                "EXPECTED_SECRET_TICK is None — run once to capture."
            )
        assert secret_tick == EXPECTED_SECRET_TICK

        assert len(new_state.ending_history) == 1
        marker = cast(dict[str, Any], new_state.ending_history[0])
        assert marker.get("kind") == "ending_triggered"
        assert marker.get("ending_type") == "SECRET"
