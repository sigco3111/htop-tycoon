"""Tests for the T45 schema v2 + v1→v2 migration.

Wave 9 (T45) — when loading a v1 save (from v0.1.0), the deserialize
layer must:

- Read ``data["version"]`` == 1.
- Call ``upgrade_v1_to_v2(data)`` which:
  * Sets ``state.regime = default RegimeState(NORMAL, 0, 0)``.
  * Sets ``state.dept_focus = {dept_id: FocusChoice(BALANCED, set_tick=0)
    for dept_id in state.departments.keys()}`` so every existing dept
    gets a default FocusChoice entry.
- Bumps ``data["version"]`` to 2.
- Continue normal deserialization at v2.

Forward compatibility: unknown v3+ fields are silently dropped.
"""

from __future__ import annotations

from htop_tycoon.domain.state import (
    GameState,
    state_hash,
)
from htop_tycoon.persistence.deserialize import deserialize
from htop_tycoon.persistence.migration import upgrade_v1_to_v2
from htop_tycoon.persistence.serialize import SCHEMA_VERSION

# ============================================================================
# Version constant
# ============================================================================


class TestSchemaVersion:
    def test_schema_version_is_2(self) -> None:
        assert SCHEMA_VERSION == 2


# ============================================================================
# upgrade_v1_to_v2
# ============================================================================


class TestUpgradeV1ToV2:
    def test_adds_regime_field_to_state(self) -> None:
        v1_data = {
            "version": 1,
            "state": _v1_envelope(),
            "saved_at_iso": "2026-06-30T00:00:00Z",
        }
        upgraded = upgrade_v1_to_v2(v1_data)
        # The state dict now carries a regime entry (default NORMAL).
        assert "regime" in upgraded["state"]
        assert upgraded["state"]["regime"]["current"] == "NORMAL"
        assert upgraded["state"]["regime"]["weeks_in_regime"] == 0
        assert upgraded["state"]["regime"]["started_tick"] == 0

    def test_adds_dept_focus_default_for_each_dept(self) -> None:
        state_envelope = _v1_envelope()
        state_envelope["departments"] = {
            "dept-a": "Department(...)",
            "dept-b": "Department(...)",
        }
        v1_data = {
            "version": 1,
            "state": state_envelope,
            "saved_at_iso": "2026-06-30T00:00:00Z",
        }
        upgraded = upgrade_v1_to_v2(v1_data)
        focus_map = upgraded["state"]["dept_focus"]
        assert "dept-a" in focus_map
        assert "dept-b" in focus_map
        assert focus_map["dept-a"]["focus"] == "BALANCED"
        assert focus_map["dept-a"]["set_tick"] == 0

    def test_no_departments_means_empty_focus_map(self) -> None:
        v1_data = {
            "version": 1,
            "state": _v1_envelope(),
            "saved_at_iso": "2026-06-30T00:00:00Z",
        }
        upgraded = upgrade_v1_to_v2(v1_data)
        assert upgraded["state"]["dept_focus"] == {}

    def test_bumps_version_to_2(self) -> None:
        v1_data = {
            "version": 1,
            "state": _v1_envelope(),
            "saved_at_iso": "2026-06-30T00:00:00Z",
        }
        upgraded = upgrade_v1_to_v2(v1_data)
        assert upgraded["version"] == 2

    def test_is_pure_no_input_mutation(self) -> None:
        v1_data = {
            "version": 1,
            "state": _v1_envelope(),
            "saved_at_iso": "2026-06-30T00:00:00Z",
        }
        original_version = v1_data["version"]
        original_state_keys = sorted(v1_data["state"].keys())
        _ = upgrade_v1_to_v2(v1_data)
        # Input payload must NOT be mutated; the upgrade produces a NEW dict.
        assert v1_data["version"] == original_version
        assert sorted(v1_data["state"].keys()) == original_state_keys, (
            "input state must not gain keys; upgrade produces a new dict"
        )


# ============================================================================
# end-to-end deserialize
# ============================================================================


class TestDeserializeEndToEnd:
    def test_v1_payload_round_trips_to_valid_v2_state(self) -> None:
        """A v1 JSON payload (no regime / dept_focus) loads to a valid
        v2 GameState with sensible defaults.
        """
        v1_payload = {
            "version": 1,
            "state": _v1_envelope(),
            "saved_at_iso": "2026-06-30T00:00:00Z",
        }
        state = deserialize(v1_payload)
        assert isinstance(state, GameState)
        assert state.regime.current.value == "NORMAL"
        # The empty departments payload gives an empty focus map.
        assert state.dept_focus == {}

    def test_v2_payload_round_trips_to_same_state_hash(self) -> None:
        """A v2 payload (with the new fields already present) loads to a
        state whose hash matches a freshly-constructed v2 default state.
        """

        from htop_tycoon.domain.state import new_game
        from htop_tycoon.persistence.serialize import serialize as _serialize

        fresh = new_game(rng_seed=42)
        v2_payload = _serialize(fresh)
        loaded = deserialize(v2_payload)
        assert state_hash(loaded) == state_hash(fresh)

    def test_unknown_version_routes_to_recovery(self) -> None:
        v99_payload = {
            "version": 99,
            "state": _v1_envelope(),
            "saved_at_iso": "2026-06-30T00:00:00Z",
        }
        state = deserialize(v99_payload)
        # Recovery path returns the corruption-recovery state (seed=0,
        # new_game). The exact state is allowed to be any valid state.
        assert isinstance(state, GameState)


# ============================================================================
# Helpers
# ============================================================================


def _v1_envelope() -> dict:
    """A minimal v1 envelope body. ``departments``/etc are kept as
    raw mapping data; deserialize handles only the parts the upgrade
    path actually inspects (state shape).
    """
    return {
        "company": {"id": "company-1", "name": "My Company", "cash": 50000, "market_cap": 50000},
        "departments": {},
        "employees": {},
        "products": {},
        "competitors": {},
        "events_active": [],
        "ending_history": [],
        "secret_investor_cleared": False,
        "tick": 0,
        "rng_seed": 42,
        "game_time": {"year": 1, "quarter": 1, "week": 1},
        "version": 1,
    }
