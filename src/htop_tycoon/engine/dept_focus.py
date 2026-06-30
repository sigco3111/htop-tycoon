"""Engine: apply_focus_modifier (Wave 8 / T41).

Pure function combining a per-department focus modifier with the active
regime multiplier and clamping the result into a safe band.

Contract (per T41 plan):

- BALANCED focus returns 1.0 in every metric.
- ``productivity`` is multiplied by ``state.regime.current``'s
  ``revenue_multiplier``.
- ``salary_growth`` is multiplied by the regime's
  ``salary_growth_multiplier``.
- ``satisfaction_delta`` is NOT regime-scaled (it's a per-tick int
  delta applied directly to employee satisfaction).
- Final modifier is clamped to ``[clamp_min, clamp_max]`` from
  balance.yaml (``departments.focus.clamp_min`` /
  ``clamp_max``; defaults: 0.5 / 2.0).
- Unknown dept_id / unknown focus returns 1.0 + warn-once log.
- Pure: no state mutation; no ``event_bus.publish``; no RNG calls.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any, cast

from htop_tycoon.domain.focus import DEFAULT_FOCUS, FocusType
from htop_tycoon.domain.state import GameState

# WARN_ONCE dedupe for unknown dept_id / unknown focus.
_WARNED_UNKNOWN: set[tuple[str, str]] = set()


def _warn_unknown(kind: str, key: str) -> None:
    pair = (kind, key)
    if pair in _WARNED_UNKNOWN:
        return
    _WARNED_UNKNOWN.add(pair)
    warnings.warn(
        f"apply_focus_modifier: {kind}={key!r} not found; defaulting to 1.0",
        stacklevel=2,
    )


# ---------------------------------------------------------------------------
# Clamp bounds, read once from balance.yaml at module import.
# ---------------------------------------------------------------------------

_CLAMP_MIN_CACHE: float = 0.5
_CLAMP_MAX_CACHE: float = 2.0


def _load_clamp_bounds(balance: Mapping[str, object]) -> None:
    """Re-read clamp bounds from balance.yaml into module cache."""
    global _CLAMP_MIN_CACHE, _CLAMP_MAX_CACHE
    depts = balance.get("departments")
    focus_block: Mapping[str, object] = {}
    if isinstance(depts, Mapping):
        inner = depts.get("focus")
        if isinstance(inner, Mapping):
            focus_block = inner
    _CLAMP_MIN_CACHE = float(cast(Any, focus_block.get("clamp_min", 0.5)))
    _CLAMP_MAX_CACHE = float(cast(Any, focus_block.get("clamp_max", 2.0)))


def effective_modifier_clamp_min() -> float:
    """Return the current clamp-min value (read once from balance.yaml)."""
    return _CLAMP_MIN_CACHE


def effective_modifier_clamp_max() -> float:
    """Return the current clamp-max value (read once from balance.yaml)."""
    return _CLAMP_MAX_CACHE


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _focus_modifiers_section(
    balance: Mapping[str, object],
) -> Mapping[str, Mapping[str, float]]:
    """Return the ``departments.focus.modifiers`` mapping from balance.

    Returns an empty mapping when keys are missing; callers translate
    missing entries into 1.0 + warn-once.
    """
    depts = balance.get("departments")
    if not isinstance(depts, Mapping):
        return {}
    focus = depts.get("focus")
    if not isinstance(focus, Mapping):
        return {}
    mods = focus.get("modifiers")
    if not isinstance(mods, Mapping):
        return {}
    out: dict[str, Mapping[str, float]] = {}
    for k, v in mods.items():
        if isinstance(v, Mapping):
            out[str(k)] = {str(mk): float(mv) for mk, mv in v.items()}
    return out


def _raw_focus_modifier(
    focus: FocusType,
    metric: str,
    modifiers: Mapping[str, Mapping[str, float]],
) -> float | None:
    """Return the raw per-focus modifier for ``metric`` or ``None``."""
    bucket = modifiers.get(focus.value)
    if bucket is None:
        return None
    val = bucket.get(metric)
    if val is None:
        return None
    return float(val)


def _regime_metric_multiplier(
    state: GameState,
    metric: str,
    balance: Mapping[str, object],
) -> float:
    """Return the regime's matching multiplier for ``metric`` (1.0 fallback)."""
    from htop_tycoon.engine.regimes import load_regimes_from_balance

    try:
        cycles = load_regimes_from_balance(cast(Any, balance))
    except (KeyError, TypeError, ValueError):
        return 1.0
    try:
        modifiers = cycles[state.regime.current].modifiers
    except (KeyError, AttributeError):
        return 1.0
    if metric == "productivity":
        return float(modifiers.revenue_multiplier)
    if metric == "salary_growth":
        return float(modifiers.salary_growth_multiplier)
    return 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_focus_modifier(
    state: GameState,
    dept_id: str,
    metric: str,
    balance: Mapping[str, object],
) -> float:
    """Return the effective multiplier for ``metric`` in ``dept_id``.

    Algorithm:
        1. Look up ``state.dept_focus[dept_id]``. Missing → 1.0.
        2. BALANCED → 1.0 (identity).
        3. Read raw modifier from
           ``balance[departments][focus][modifiers][focus][metric]``.
        4. Multiply by regime's matching multiplier
           (only productivity + salary_growth).
        5. Clamp to ``[clamp_min, clamp_max]``.

    Pure function. No state mutation; no event publication; no RNG.
    """
    # Refresh clamp bounds on each call (small, in-memory read).
    _load_clamp_bounds(balance)

    # Step 1: dept focus lookup.
    if not isinstance(state.dept_focus, Mapping):
        _warn_unknown("state.dept_focus", "(none)")
        return 1.0
    focus_choice = state.dept_focus.get(dept_id)
    if focus_choice is None:
        _warn_unknown("dept_id", dept_id)
        return 1.0

    # Step 2: BALANCED short-circuit.
    focus = focus_choice.focus
    if focus is DEFAULT_FOCUS:
        return 1.0

    # Step 3: raw modifier from balance.
    modifiers = _focus_modifiers_section(balance)
    raw = _raw_focus_modifier(focus, metric, modifiers)
    if raw is None:
        _warn_unknown("focus_or_metric", f"{focus.value}.{metric}")
        return 1.0

    # Step 4: regime multiplier (productivity + salary_growth only).
    regime_factor = 1.0
    if metric in ("productivity", "salary_growth"):
        regime_factor = _regime_metric_multiplier(state, metric, balance)

    effective = raw * regime_factor
    # Step 5: clamp.
    clamped = max(_CLAMP_MIN_CACHE, min(_CLAMP_MAX_CACHE, effective))
    return clamped


__all__ = [
    "apply_focus_modifier",
    "effective_modifier_clamp_max",
    "effective_modifier_clamp_min",
]
