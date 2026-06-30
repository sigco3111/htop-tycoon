"""Wave 8 / T44 — regime-aware focus heuristic + apply function.

The full AutoManager (``engine/ai_manager``) is the consumer of these
helpers: when ``state._delegated`` is true and the cooldown guard
allows, the engine tick orchestrator dispatches a focus change via
:func:`apply_ai_suggested_focus`.

This module is split out from ``ai_manager.decide()`` so the heuristic
is unit-testable in isolation; the AutoManager module can call into
it without depending on Textual or the App.

Anti-patterns honoured:
- No ``event_bus.publish`` calls (pure return).
- No state mutation; ``apply_ai_suggested_focus`` returns a new
  ``GameState`` via ``dataclasses.replace``.
- No magic numbers; cash thresholds read from balance.yaml under a
  new ``ai_focus_policy`` block (defaults below when missing).
"""

from __future__ import annotations

from collections.abc import Mapping

from htop_tycoon.domain.focus import FocusType
from htop_tycoon.domain.regimes import RegimeType
from htop_tycoon.domain.state import GameState
from htop_tycoon.engine.events import Event
from htop_tycoon.ui.screens.focus_picker import (
    FocusChanged,
    apply_focus_change,
    can_change_focus,
)

# ============================================================================
# Cash thresholds (locked for T44; future balance.yaml keys optional)
# ============================================================================

_LOW_CASH_THRESHOLD_DEFAULT: int = 5_000
_HIGH_CASH_THRESHOLD_DEFAULT: int = 50_000


def _cash_thresholds(balance: Mapping[str, object]) -> tuple[int, int]:
    """Read ``ai_focus_policy.low_cash_threshold`` and ``high_cash_threshold``.

    Falls back to plan defaults when the balance block is missing.
    """
    block = balance.get("ai_focus_policy")
    if not isinstance(block, Mapping):
        return _LOW_CASH_THRESHOLD_DEFAULT, _HIGH_CASH_THRESHOLD_DEFAULT
    low = int(block.get("low_cash_threshold", _LOW_CASH_THRESHOLD_DEFAULT))
    high = int(block.get("high_cash_threshold", _HIGH_CASH_THRESHOLD_DEFAULT))
    return low, high


# ============================================================================
# Per-dept focus maps for CRISIS (cost-like) and BOOM (growth-like)
# ============================================================================

_CRISIS_COST_FOCUS_PER_DEPT: dict[str, FocusType] = {
    "Engineering": FocusType.COST,
    "Sales": FocusType.CONSERVATIVE,
    "Operations": FocusType.EFFICIENCY,
    "Marketing": FocusType.BRAND,
    "Finance": FocusType.HEDGE,
}

_BOOM_GROWTH_FOCUS_PER_DEPT: dict[str, FocusType] = {
    "Engineering": FocusType.SPEED,
    "Sales": FocusType.AGGRESSIVE,
    "Operations": FocusType.SCALE,
    "Marketing": FocusType.VIRAL,
    "Finance": FocusType.GROWTH,
}


def _dept_type_name_from_state(state: GameState, dept_id: str) -> str | None:
    """Return the dept-type NAME (str) for ``dept_id``, or None."""
    if not isinstance(state.departments, Mapping):
        return None
    raw_dept = state.departments.get(dept_id)  # type: ignore[call-overload]
    if raw_dept is None:
        return None
    # raw_dept is typed dict[K, Any]; type field is the dept-type enum.
    dept_type = getattr(raw_dept, "type", None)
    if dept_type is None:
        return None
    name = getattr(dept_type, "name", None)
    if not isinstance(name, str):
        return None
    return name


# ============================================================================
# Pure functions
# ============================================================================


def regime_aware_focus_suggestion(
    state: GameState, dept_id: str, balance: Mapping[str, object]
) -> FocusType:
    """Return the focus the Auto-Manager would set for ``dept_id``.

    Algorithm (locked T44 contract):
        * CRISIS regime + cash below ``low_cash_threshold`` → cost-like focus.
        * CRISIS regime + cash above ``low_cash_threshold`` → still cost-like
          (regime dominates; cash modulation is a future wave).
        * BOOM regime + cash above ``high_cash_threshold`` → growth-like focus.
        * BOOM + low cash → BALANCED (no aggressive growth with thin wallet).
        * NORMAL (or unknown) → BALANCED.

    Pure: no state mutation; no event publication.
    """
    regime = state.regime.current
    cash = state.company.cash
    low, _high = _cash_thresholds(balance)
    dept_type_name = _dept_type_name_from_state(state, dept_id)

    if regime is RegimeType.CRISIS:
        if cash < low:
            target = (
                _CRISIS_COST_FOCUS_PER_DEPT.get(dept_type_name or "", FocusType.BALANCED)
                if dept_type_name
                else FocusType.CONSERVATIVE_FIN
            )
            return target
        # CRISIS at high cash still picks cost-like (defensive).
        return (
            _CRISIS_COST_FOCUS_PER_DEPT.get(dept_type_name or "", FocusType.BALANCED)
            if dept_type_name
            else FocusType.CONSERVATIVE_FIN
        )
    if regime is RegimeType.BOOM and cash > _HIGH_CASH_THRESHOLD_DEFAULT:
        return (
            _BOOM_GROWTH_FOCUS_PER_DEPT.get(dept_type_name or "", FocusType.BALANCED)
            if dept_type_name
            else FocusType.GROWTH
        )
    return FocusType.BALANCED


def apply_ai_suggested_focus(
    state: GameState,
    balance: Mapping[str, object],
    current_tick: int,
) -> tuple[GameState, list[Event]]:
    """Apply the AI's regime-aware focus suggestion across all depts.

    For each department:
      1. Compute :func:`regime_aware_focus_suggestion` for the dept.
      2. If the suggestion is ``BALANCED`` OR ``can_change_focus`` is
         False OR the suggested focus equals the current focus → skip.
      3. Otherwise call :func:`apply_focus_change` and append one
         ``FocusChanged`` engine signal.

    Returns ``(new_state, signals)``. ``new_state`` is the input state
    UNCHANGED if no changes were applied (skip-only paths).
    """
    low, high = _cash_thresholds(balance)
    _ = (low, high)  # thresholds read but currently not branched on
    if not isinstance(state.departments, Mapping):
        return state, []

    current_state = state
    signals: list[Event] = []
    for dept_id_str in state.departments:
        # Suggest
        suggestion = regime_aware_focus_suggestion(current_state, dept_id_str, balance)
        if suggestion is FocusType.BALANCED:
            continue
        # Cooldown guard
        if not can_change_focus(current_state, dept_id_str, current_tick, balance):
            continue
        # Skip if already the suggested focus.
        existing_focus = current_state.dept_focus.get(dept_id_str)
        if existing_focus is not None and existing_focus.focus is suggestion:
            continue
        prev_focus = existing_focus.focus if existing_focus is not None else FocusType.BALANCED
        # Apply
        new_state_obj = apply_focus_change(
            current_state,
            dept_id_str,
            new_focus=suggestion,
            current_tick=current_tick,
            balance=balance,
        )
        signals.append(
            FocusChanged(
                kind="focus_changed",
                dept_id=dept_id_str,
                prev=prev_focus,
                next=suggestion,
                tick=current_tick,
            )
        )
        current_state = new_state_obj
    return current_state, signals


__all__ = [
    "apply_ai_suggested_focus",
    "regime_aware_focus_suggestion",
]
