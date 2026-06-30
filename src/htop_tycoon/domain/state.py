"""Domain: GameState aggregate, Company, GameTime, serialization helpers.

Pure data only. The engine produces new states via ``dataclasses.replace``;
the UI reads states; persistence writes them. State is the single source of
truth and is strictly frozen.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any, Literal, NewType

from htop_tycoon.data import load_balance
from htop_tycoon.domain.regimes import RegimeState, default_regime_state

__all__ = [
    "Company",
    "CompetitorId",
    "DepartmentId",
    "EmployeeId",
    "EventId",
    "GameState",
    "GameTime",
    "ProductId",
    "RegimeState",
    "StoryNodeId",
    "default_regime_state",
    "new_game",
    "state_hash",
]

# ID types: NewType prevents accidental ID confusion across domains.
# At runtime these are plain ``str``; the type checker treats them as
# distinct nominal types.
DepartmentId = NewType("DepartmentId", str)
EmployeeId = NewType("EmployeeId", str)
ProductId = NewType("ProductId", str)
CompetitorId = NewType("CompetitorId", str)
EventId = NewType("EventId", str)
StoryNodeId = NewType("StoryNodeId", str)


def _require_strict_int(name: str, value: object) -> int:
    """Validate that ``value`` is a built-in ``int`` (rejecting ``bool`` and ``float``)."""
    # ``bool`` is a subclass of ``int`` in Python; reject it explicitly so
    # ``True``/``False`` cannot silently sneak into numeric fields.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{name} must be a strict int, got {type(value).__name__}: {value!r}"
        )
    return value


def _validate_company_market_cap(value: object) -> int:
    """Validate Company.market_cap: strict int, >= 0."""
    validated = _require_strict_int("market_cap", value)
    if validated < 0:
        raise ValueError(f"market_cap must be non-negative, got {validated!r}")
    return value


def _validate_company_cash(value: object) -> int:
    """Validate Company.cash: strict int (negative allowed for debt)."""
    return _require_strict_int("cash", value)


def _validate_game_time_year(value: object) -> int:
    return _require_strict_int("year", value)


def _validate_game_time_quarter(value: object) -> int:
    validated = _require_strict_int("quarter", value)
    if not 1 <= validated <= 4:
        raise ValueError(f"quarter must be in [1, 4], got {validated!r}")
    return validated


def _validate_game_time_week(value: object) -> int:
    validated = _require_strict_int("week", value)
    if not 1 <= validated <= 52:
        raise ValueError(f"week must be in [1, 52], got {validated!r}")
    return validated


@dataclasses.dataclass(frozen=True, slots=True)
class Company:
    """The player-owned company. Pure data; no business logic here.

    Attributes:
        id: Stable identifier (e.g. ``"company-1"``).
        name: Display name (Korean or English; no formatting here).
        cash: Current cash balance. May be negative (debt, bankruptcy scenarios).
        market_cap: Total market capitalization, eagerly computed by the engine
            as ``cash + sum(product.revenue_per_week * 52)`` on every product
            state change. Must be a non-negative integer.
    """

    id: str
    name: str
    cash: int
    market_cap: int

    def __post_init__(self) -> None:
        _validate_company_cash(self.cash)
        _validate_company_market_cap(self.market_cap)


@dataclasses.dataclass(frozen=True, slots=True)
class GameTime:
    """Game time: ``year`` + ``quarter`` + ``week``.

    - ``year`` is an unbounded counter (starts at 1).
    - ``quarter`` is in [1, 4].
    - ``week`` is in [1, 52] (4 quarters x 13 weeks).
    """

    year: int
    quarter: int
    week: int

    def __post_init__(self) -> None:
        _validate_game_time_year(self.year)
        _validate_game_time_quarter(self.quarter)
        _validate_game_time_week(self.week)


@dataclasses.dataclass(frozen=True, slots=True)
class GameState:
    """The authoritative game state aggregate. Strictly frozen.

    The engine produces new states via ``dataclasses.replace``. The UI only
    reads; persistence only writes. State is the single source of truth.
    """

    company: Company
    departments: dict[DepartmentId, Any]
    employees: dict[EmployeeId, Any]
    products: dict[ProductId, Any]
    competitors: dict[CompetitorId, Any]
    events_active: list[Any]
    ending_history: list[Any]
    secret_investor_cleared: bool = False
    tick: int = 0
    rng_seed: int = 0
    game_time: GameTime = dataclasses.field(
        default_factory=lambda: GameTime(year=1, quarter=1, week=1)
    )
    regime: RegimeState = dataclasses.field(default_factory=default_regime_state)
    version: Literal[1] = 1


def new_game(rng_seed: int) -> GameState:
    """Create a fresh game state with empty departments/employees/etc.

    ``cash`` is sourced from ``balance.yaml`` (``money.starting_cash``). The
    initial ``market_cap`` equals ``cash`` because there are no products yet
    (so the revenue component is zero). The engine is responsible for
    re-deriving ``market_cap`` on every product state change.
    """
    balance = load_balance()
    starting_cash = int(balance["money"]["starting_cash"])
    company = Company(
        id="company-1",
        name="My Company",
        cash=starting_cash,
        market_cap=starting_cash,
    )
    return GameState(
        company=company,
        departments={},
        employees={},
        products={},
        competitors={},
        events_active=[],
        ending_history=[],
        secret_investor_cleared=False,
        tick=0,
        rng_seed=rng_seed,
        game_time=GameTime(year=1, quarter=1, week=1),
        regime=default_regime_state(),
        version=1,
    )


def state_hash(state: GameState) -> str:
    """SHA-256 hex digest of the canonical JSON of ``state``.

    Canonical form: ``json.dumps(dataclasses.asdict(state), sort_keys=True,
    default=str)``. ``sort_keys=True`` and ``default=str`` make the output
    stable across runs and Python versions.
    """
    payload = json.dumps(
        dataclasses.asdict(state), sort_keys=True, default=str
    ).encode()
    return hashlib.sha256(payload).hexdigest()
