"""Auto-execute — runs all AI decisions for one tick.

Pure function. Returns new CompanyState, input untouched. Called by tick()
when state.auto_on is True; replaces _apply_strategy_decisions in that path.

Steps (in order):
1. Re-pick strategy via pick_strategy
2. Auto-hire best candidate if strategy says hire and conditions allow
3. Auto-fire lowest-stat employee if cash low and zombies exist
4. Auto-release shipped project on cheapest non-owned console
5. Auto-buy cheapest affordable console if no own console and cash ≥ $80k
6. Auto-request voluntary sale if mega_hit or hall_of_fame and cash ≥ $200k
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from htop_tycoon.domain.enums import StrategyKind
from htop_tycoon.engine.console_market import (
    CONSOLE_PRICES,
    available_consoles,
    purchase_console,
)
from htop_tycoon.engine.event_log import Event, EventKind
from htop_tycoon.engine.hr import (
    fire_employee,
    generate_candidates,
    hire_employee,
)
from htop_tycoon.engine.market import MarketState
from htop_tycoon.engine.release import release_project, releaseable_projects
from htop_tycoon.engine.strategy.dispatch import current_strategy
from htop_tycoon.engine.strategy.meta_strategy import (
    CASH_LOW_CENTS,
    pick_strategy,
)

if TYPE_CHECKING:
    from htop_tycoon.domain.rng import GameRng
    from htop_tycoon.domain.state import CompanyState

AUTO_CONSOLE_BUY_MIN_CASH_CENTS: int = 80_000_00
AUTO_VOLUNTARY_SALE_MIN_CENTS: int = 200_000_00
AUTO_HIRE_MIN_HEADCOUNT: int = 10


@dataclass(frozen=True, slots=True)
class AutoAction:
    """Record of a single auto-executed decision for the event log."""

    kind: EventKind
    description: str


def _append(state: CompanyState, kind: EventKind, description: str) -> CompanyState:
    return state.append_event(
        Event(
            day_index=state.day_index,
            year=state.year,
            kind=kind,
            description=description,
        )
    )


def auto_execute(
    state: CompanyState,
    rng: GameRng,
    market: MarketState,
) -> CompanyState:
    """Run all AI decisions for one tick and return new CompanyState."""
    new_state = state

    new_strategy = pick_strategy(new_state, rng)
    if new_strategy != new_state.strategy:
        new_state = new_state.set_strategy(new_strategy)
        new_state = _append(
            new_state, EventKind.STRATEGY_CHANGED, f"전략 변경: {new_strategy.value}"
        )

    strategy = current_strategy(new_state)
    decisions = strategy.decide(new_state, rng)
    decision_actions = {d.action for d in decisions}

    if "hire" in decision_actions:
        if len(new_state.employees) < AUTO_HIRE_MIN_HEADCOUNT:
            candidates = generate_candidates(
                rng,
                count=5,
                used_names={e.name for e in new_state.employees.values()},
            )
            if candidates:
                best = max(candidates, key=lambda c: c.suggested_level)
                new_state = hire_employee(new_state, best)
                new_state = _append(
                    new_state,
                    EventKind.HIRE,
                    f"고용: {best.name} ({best.job.value} L{best.suggested_level})",
                )

    if new_state.cash.cents < CASH_LOW_CENTS:
        zombies = [
            e for e in new_state.employees.values() if e.is_zombie
        ]
        if zombies:
            worst = min(zombies, key=lambda e: e.satisfaction)
            new_state = fire_employee(new_state, worst.id)
            new_state = _append(
                new_state, EventKind.FIRE, f"해고: {worst.name} (좀비)"
            )

    releasable = releaseable_projects(new_state)
    if releasable:
        target = next(
            (c for c in available_consoles() if c != new_state.own_console),
            None,
        )
        if target is not None:
            project = releasable[0]
            try:
                new_state = release_project(
                    new_state, project.id, target, market, rng
                )
                new_state = _append(
                    new_state,
                    EventKind.RELEASE,
                    f"출시: {project.title} → {target.value}",
                )
            except ValueError:
                pass

    if (
        new_state.own_console is None
        and new_state.cash.cents >= AUTO_CONSOLE_BUY_MIN_CASH_CENTS
    ):
        affordable = sorted(
            [
                c
                for c in available_consoles()
                if CONSOLE_PRICES[c] <= new_state.cash.cents
            ],
            key=lambda c: CONSOLE_PRICES[c],
        )
        if affordable:
            console = affordable[0]
            new_state = purchase_console(new_state, console)
            new_state = _append(
                new_state,
                EventKind.PURCHASE_CONSOLE,
                f"콘솔 구매: {console.value}",
            )

    if (
        new_state.cash.cents >= AUTO_VOLUNTARY_SALE_MIN_CENTS
        and new_state.mega_hits >= 1
    ):
        new_state = new_state.set_voluntary_sale_pending(True)
        new_state = _append(
            new_state, EventKind.VOLUNTARY_SALE, "자발적 매각 요청"
        )

    return new_state