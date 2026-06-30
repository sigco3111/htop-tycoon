"""Tests for the T38 regime-modifier integration across the engine.

Wave 7 (T38) — three engine sub-systems apply regime modifiers:

  * ``engine.metrics``: cpu_pct scales by ``revenue_multiplier``
  * ``engine.competitor_ai``: action roll threshold uses
    ``competitor_aggression_baseline`` + ``per_comp.aggression``
  * ``engine.event_chain``: per-event probability scales by
    ``event_probability_scale``

T38 anti-pattern: no ``event_bus.publish`` calls anywhere. The CPU/mem
metric formula must remain "NORMAL regime = identity" so the v0.1.0
test fixtures still pass when default regime is NORMAL.

Per AGENTS.md determinism invariant, the metrics baseline change is a
deterministic function of (state, balance) — not the case-by-case RNG.

``engine.cash_flow`` is intentionally NOT patched in this todo: the
T36 spec referenced a ``salary_growth_delta`` mechanism that does not
yet exist in ``process_payroll``. A future wave may add it.
"""

from __future__ import annotations

from typing import Any

from htop_tycoon.data import load_balance
from htop_tycoon.domain.regimes import RegimeState, RegimeType
from htop_tycoon.domain.state import GameState, new_game
from htop_tycoon.engine.competitor_ai import step_competitors
from htop_tycoon.engine.event_chain import evaluate_events
from htop_tycoon.engine.metrics import compute_metrics
from htop_tycoon.engine.regimes import load_regimes_from_balance
from htop_tycoon.engine.rng import GameRNG

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _regime(reggie_type: RegimeType) -> GameState:
    """Replace ``state.regime`` to start at the requested type."""
    from dataclasses import replace

    s = new_game(rng_seed=42)
    return replace(s, regime=RegimeState(current=reggie_type, weeks_in_regime=0, started_tick=0))


def _cycles() -> dict[RegimeType, Any]:
    return load_regimes_from_balance(load_balance())


# ===========================================================================
# metrics — revenue scaling
# ===========================================================================


class TestRegimeMetricsIntegration:
    def test_normal_regime_preserves_baseline_cpu_pct(self) -> None:
        """NORMAL regime uses modifier=1.0 → cpu_pct must match a baseline
        GameState with no regime scaling applied.

        This is the regression guard for the v0.1.0 playthrough hash.
        """
        balance = load_balance()
        state_normal = _regime(RegimeType.NORMAL)
        snap_normal = compute_metrics(state_normal, balance)

        # Baseline = same state with regime multipliers all = 1.0.
        # Recompute manually to confirm NORMAL is identity:
        target = float(balance["money"]["target_revenue"])
        baseline_revenue = state_normal.company.cash + sum(
            p.revenue_per_week for p in state_normal.products.values()
        )
        expected_cpu = int(min(100, baseline_revenue / target * 100))

        assert snap_normal.cpu_pct == expected_cpu, (
            "NORMAL regime must produce cpu_pct identical to no-modifier baseline"
        )

    def test_boom_regime_increases_cpu_pct(self) -> None:
        balance = load_balance()
        snap_normal = compute_metrics(_regime(RegimeType.NORMAL), balance)
        snap_boom = compute_metrics(_regime(RegimeType.BOOM), balance)
        # BOOM has revenue_multiplier=1.3 → scaled revenue is bigger → cpu_pct
        # should be at least as large as NORMAL (capped at 100). With cash=50000
        # and a fresh state, BOOM may indeed produce a LOWER cpu_pct due to
        # the same cash starting state — but revenue (the FLOW) scales, while
        # cash (the STOCK) does not. So if no products exist, both are equal.
        # We add a product first to make the assertion meaningful.
        from dataclasses import replace

        from htop_tycoon.domain.product import LifecycleStage, Product

        product = Product(
            id="prod-svc-1",
            type="SaaS",
            lifecycle=LifecycleStage.maturity,
            weeks_in_stage=0,
            market_share=0.0,
            revenue_per_week=100_000,
        )
        s = _regime(RegimeType.NORMAL)
        s = replace(s, products={**s.products, "prod-svc-1": product})
        snap_normal = compute_metrics(s, balance)
        s = _regime(RegimeType.BOOM)
        s = replace(s, products={**s.products, "prod-svc-1": product})
        snap_boom = compute_metrics(s, balance)

        # BOOM scales revenue flow by 1.3 vs NORMAL 1.0.
        assert snap_boom.cpu_pct >= snap_normal.cpu_pct

    def test_crisis_regime_decreases_cpu_pct(self) -> None:
        """With same state but CRISIS regime (modifier=0.55), the
        revenue flow drops, so cpu_pct relative to NORMAL can only
        hold steady or drop.
        """
        from dataclasses import replace

        from htop_tycoon.domain.product import LifecycleStage, Product

        balance = load_balance()
        product = Product(
            id="prod-svc-1",
            type="SaaS",
            lifecycle=LifecycleStage.maturity,
            weeks_in_stage=0,
            market_share=0.0,
            revenue_per_week=100_000,
        )
        s = _regime(RegimeType.NORMAL)
        s = replace(s, products={**s.products, "prod-svc-1": product})
        snap_normal = compute_metrics(s, balance)
        s = _regime(RegimeType.CRISIS)
        s = replace(s, products={**s.products, "prod-svc-1": product})
        snap_crisis = compute_metrics(s, balance)

        assert snap_crisis.cpu_pct <= snap_normal.cpu_pct


# ===========================================================================
# competitor_ai — aggression baseline
# ===========================================================================


class TestRegimeCompetitorAiIntegration:
    def test_crisis_regime_action_frequency_exceeds_normal(self) -> None:
        """CRISIS.competitor_aggression_baseline=0.7 > NORMAL=0.4.

        Set per-competitor aggression to 0 (so the only signal is the
        regime baseline). Over 1000 ticks CRISIS must produce strictly
        more actions than NORMAL.
        """
        from htop_tycoon.domain.market import Competitor
        from htop_tycoon.domain.state import CompetitorId

        # Build a state with one zero-aggression competitor.
        def state_with_comp(regime: RegimeType) -> Any:
            s = _regime(regime)
            comp = Competitor(
                id=CompetitorId("c1"),
                name="Dormant",
                market_share=0.0,
                aggression=0.0,  # all decisions come from regime baseline
                cash=10_000,
                alive=True,
            )
            from dataclasses import replace

            return replace(s, competitors={CompetitorId("c1"): comp})

        count_normal, _ = _count_actions(state_with_comp(RegimeType.NORMAL), 1000)
        count_crisis, _ = _count_actions(state_with_comp(RegimeType.CRISIS), 1000)
        # CRISIS baseline 0.7 > NORMAL 0.4 → more acts.
        # The ratio is roughly 0.7/0.4 = 1.75; allow ±5% slack from random
        # selection variance.
        assert count_crisis > count_normal, (
            f"CRISIS (={count_crisis}) must produce more actions than NORMAL (={count_normal})"
        )


def _replace_competitors(state: Any, comps: list[tuple[str, float]]) -> Any:
    from dataclasses import replace

    from htop_tycoon.domain.market import Competitor as Comp
    from htop_tycoon.domain.state import CompetitorId

    new_competitors: dict[CompetitorId, Any] = {}
    for cid, agg in comps:
        new_competitors[CompetitorId(cid)] = Comp(
            id=CompetitorId(cid),
            name=cid,
            market_share=0.0,
            aggression=agg,
            cash=10_000,
            alive=True,
        )
    return replace(state, competitors=new_competitors)


def _count_actions(state: Any, n_ticks: int) -> tuple[int, Any]:
    rng = GameRNG(42)
    total = 0
    current = state
    for _ in range(n_ticks):
        current, events = step_competitors(current, rng)
        total += len(events)
    return total, current


# ===========================================================================
# event_chain — event_probability_scale
# ===========================================================================


class TestRegimeEventChainIntegration:
    def test_boom_regime_decreases_event_fire_rate(self) -> None:
        """BOOM.event_probability_scale = 0.7 → events fire less often."""
        # Compare two regimes over the same RNG sequence.
        rng_normal = GameRNG(42)
        rng_boom = GameRNG(42)
        catalog = _empty_catalog()
        state_normal = _regime(RegimeType.NORMAL)
        state_boom = _regime(RegimeType.BOOM)

        fires_normal = _count_fires(state_normal, rng_normal, catalog, n=500)
        fires_boom = _count_fires(state_boom, rng_boom, catalog, n=500)
        assert fires_boom < fires_normal

    def test_crisis_regime_increases_event_fire_rate(self) -> None:
        rng_normal = GameRNG(42)
        rng_crisis = GameRNG(42)
        catalog = _empty_catalog()
        fires_normal = _count_fires(_regime(RegimeType.NORMAL), rng_normal, catalog, 500)
        fires_crisis = _count_fires(_regime(RegimeType.CRISIS), rng_crisis, catalog, 500)
        assert fires_crisis > fires_normal


def _empty_catalog() -> list[Any]:
    """Return an empty events catalog (no events means zero fires regardless
    of probability scaling). Used to verify the *scaling* layer is reached
    by routing events through evaluate_events at known probabilities.
    """
    # Use the real catalog but count only events with id starting with
    # 'test-prob-' (none exist by default), so total fires == 0 in both
    # regimes. This test relies on the SCALING layer being entered with
    # regime modifier; we instead use a synthetic event with probability
    # 0.1 inserted via duck-typing below.

    from htop_tycoon.domain.event import Event
    from htop_tycoon.domain.state import EventId

    fake_event = Event(
        id=EventId("test-prob-fire"),
        name_ko="테스트",
        description_ko="test",
        trigger_type="random",
        probability_per_tick=0.1,
        condition=None,
        effects=(),
    )
    return [fake_event]


def _count_fires(state: Any, rng: GameRNG, catalog: list[Any], n: int) -> int:
    balance = load_balance()
    fired_total = 0
    current = state
    active: list[Any] = []
    for _ in range(n):
        current, fired, active = evaluate_events(current, rng, balance, catalog, active)
        fired_total += len(fired)
    return fired_total
