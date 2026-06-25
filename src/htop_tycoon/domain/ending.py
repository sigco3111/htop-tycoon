"""Domain: ending evaluators and the 5-locked EndingType enum.

Contract (locked by .omo/plans/htop-tycoon.md line 265-280):

- Exactly 5 endings: BANKRUPTCY, IPO, HOSTILE_MA, VOLUNTARY_SALE, SECRET.
- Each ``EndingCondition`` evaluator is a pure function ``(state, ctx) -> bool``.
- All numeric thresholds are read from ``balance.yaml`` at evaluation time;
  NO magic numbers in this file.
- ``VOLUNTARY_SALE`` requires a transient ``player_action`` carried on a
  separate ``EvaluationContext`` (NOT stored on ``GameState``).
- ``SECRET`` uses ``balance["employees"]["max_skill"]`` — never satisfaction.

Engine-level priority and dispatch live in ``engine/ending.py`` (T15);
this module is data + pure evaluators only.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable

from htop_tycoon.data import load_balance
from htop_tycoon.domain.state import GameState

__all__ = [
    "ALL_ENDINGS",
    "BANKRUPTCY",
    "EndingCondition",
    "EndingType",
    "EvaluationContext",
    "HOSTILE_MA",
    "IPO",
    "SECRET",
    "VOLUNTARY_SALE",
]


class EndingType(enum.Enum):
    """The locked 5-ending enum. Names == values (string identity)."""

    BANKRUPTCY = "BANKRUPTCY"
    IPO = "IPO"
    HOSTILE_MA = "HOSTILE_MA"
    VOLUNTARY_SALE = "VOLUNTARY_SALE"
    SECRET = "SECRET"


@dataclasses.dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Transient evaluation context passed alongside ``GameState`` to evaluators.

    Holds per-tick or per-action transient data that must NOT be persisted on
    ``GameState``. The single canonical field today is ``player_action``, set
    by the T25 handler for one-tick windows.
    """

    player_action: str | None = None


# Evaluator signature: pure function over (state, ctx).
_Evaluator = Callable[[GameState, EvaluationContext], bool]


@dataclasses.dataclass(frozen=True, slots=True)
class EndingCondition:
    """An ending + its pure evaluator.

    ``evaluate(state, ctx) -> bool`` is the contract. Priority / dispatch
    (which ending wins when multiple fire) lives in ``engine/ending.py``.
    """

    ending_type: EndingType
    evaluate: _Evaluator


# ---------------------------------------------------------------------------
# Pure evaluators — read thresholds from balance.yaml, no magic numbers.
# ---------------------------------------------------------------------------


def _bankruptcy(state: GameState, ctx: EvaluationContext) -> bool:
    """Trigger when company cash falls strictly below the bankruptcy floor."""
    floor = load_balance()["money"]["bankruptcy_cash_floor"]
    return state.company.cash < int(floor)


def _ipo(state: GameState, ctx: EvaluationContext) -> bool:
    """Trigger when market_cap hits the IPO threshold AND cash is positive."""
    balance = load_balance()
    threshold = int(balance["endings"]["ipo_market_cap_threshold"])
    return state.company.market_cap >= threshold and state.company.cash > 0


def _hostile_ma(state: GameState, ctx: EvaluationContext) -> bool:
    """Trigger when any ALIVE competitor has more cash than us AND
    an aggression strictly above the hostility threshold.
    """
    balance = load_balance()
    threshold = float(balance["endings"]["hostile_ma_trigger_competitor_aggression"])
    return any(
        competitor.cash >= state.company.market_cap
        and competitor.aggression > threshold
        for competitor in state.competitors.values()
        if competitor.alive
    )


def _voluntary_sale(state: GameState, ctx: EvaluationContext) -> bool:
    """Trigger only when the player explicitly chose to sell AND cash
    is at or above the voluntary-sale minimum. The ``player_action``
    transient is set by the T25 handler; it never lives on ``GameState``.
    """
    balance = load_balance()
    min_cash = int(balance["endings"]["voluntary_sale_min_cash"])
    return (
        ctx.player_action == "sell"
        and state.company.cash >= min_cash
    )


def _secret(state: GameState, ctx: EvaluationContext) -> bool:
    """Trigger when ALL three sub-conditions hold:

    1. Every department is unlocked.
    2. Every employee's ``skill`` equals ``balance["employees"]["max_skill"]``.
    3. ``state.secret_investor_cleared`` is True (flipped on player resolution).

    The skill sub-condition uses ``max_skill`` (NOT satisfaction) — that
    is the locked contract from plan line 271.
    """
    balance = load_balance()
    max_skill = int(balance["employees"]["max_skill"])
    return (
        all(dept.unlocked for dept in state.departments.values())
        and all(emp.skill == max_skill for emp in state.employees.values())
        and state.secret_investor_cleared
    )


# ---------------------------------------------------------------------------
# Concrete EndingCondition instances (exactly 5, locked).
# ---------------------------------------------------------------------------


BANKRUPTCY = EndingCondition(EndingType.BANKRUPTCY, _bankruptcy)
IPO = EndingCondition(EndingType.IPO, _ipo)
HOSTILE_MA = EndingCondition(EndingType.HOSTILE_MA, _hostile_ma)
VOLUNTARY_SALE = EndingCondition(EndingType.VOLUNTARY_SALE, _voluntary_sale)
SECRET = EndingCondition(EndingType.SECRET, _secret)


ALL_ENDINGS: tuple[EndingCondition, ...] = (
    BANKRUPTCY,
    IPO,
    HOSTILE_MA,
    VOLUNTARY_SALE,
    SECRET,
)
