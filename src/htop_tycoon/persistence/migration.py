"""T45: v1->v2 migration + version constant bump.

This module contains the ONE migration :func:`upgrade_v1_to_v2` that
takes a v1 envelope and returns a NEW dict carrying the v2 fields:

  * ``state.regime`` is set to a default
    :class:`RegimeState` (NORMAL/0/0).
  * ``state.dept_focus`` is set to ``{dept_id: FocusChoice(BALANCED,
    set_tick=0) for dept_id in state.departments}``.
  * ``version`` is bumped from 1 to 2.

The function is PURE: it takes a dict, returns a NEW dict. The input
must NOT be mutated (T45 tests pin this).

Forward-compatibility policy: callers (the deserialize layer) drop
unrecognized fields at deserialization time. This module therefore
does not need to handle "v3 fields leak through" — once a future
schema writes an unknown field, deserialize simply ignores it.
"""

from __future__ import annotations

from typing import Any

# v1 has NO ``regime`` / ``dept_focus`` fields. v2 introduces both.
# This module is the single source of truth for that delta.
_TARGET_SCHEMA_VERSION: int = 2
_DEFAULT_REGIME = {
    "current": "NORMAL",
    "weeks_in_regime": 0,
    "started_tick": 0,
}


def upgrade_v1_to_v2(v1_data: dict[str, Any]) -> dict[str, Any]:
    """Return a NEW dict upgraded from v1 to v2.

    Adds:
      * ``state.regime`` -> default RegimeState (NORMAL/0/0).
      * ``state.dept_focus`` -> {every dept_id: BALANCED, set_tick=0}.
      * ``version`` -> 2 (mutation only on the returned dict, not the
        input).

    Preserves every other field (``company``, ``game_time``, etc.) by
    shallow-copying the state sub-dict and adding the new keys.
    """
    state = dict(v1_data["state"])  # shallow copy
    departments = state.get("departments") or {}
    if not isinstance(departments, dict):
        departments = {}
    focus_map: dict[str, dict[str, Any]] = {
        str(dept_id): {"focus": "BALANCED", "set_tick": 0} for dept_id in departments.keys()
    }
    state["regime"] = dict(_DEFAULT_REGIME)
    state["dept_focus"] = focus_map
    # Shallow-copy the top-level payload too.
    return {
        **v1_data,
        "version": _TARGET_SCHEMA_VERSION,
        "state": state,
    }


__all__ = ["upgrade_v1_to_v2"]
