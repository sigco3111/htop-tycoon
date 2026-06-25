"""Tests for T3: balance.yaml tunables and load_balance helper.

Given / When / Then is structured per test for clarity.
The `balance` fixture is loaded once per class via lru_cache; tests assert
observable structure, not implementation details.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from htop_tycoon.data import REQUIRED_TOP_LEVEL_KEYS, load_balance

if TYPE_CHECKING:
    from collections.abc import Mapping


class TestLoadBalanceHelper:
    """load_balance() returns parsed YAML and is cached after first call."""

    def test_returns_dict(self) -> None:
        """Given: load_balance() is callable
        When: called
        Then: returns a dict
        """
        result = load_balance()
        assert isinstance(result, dict)

    def test_cached_returns_same_object(self) -> None:
        """Given: load_balance has been called once
        When: called again
        Then: returns the exact same object (lru_cache identity)
        """
        first = load_balance()
        second = load_balance()
        assert first is second

    def test_all_required_top_level_keys_present(self) -> None:
        """Given: a valid balance.yaml
        When: load_balance() is called
        Then: every required top-level key is present
        """
        balance = load_balance()
        missing = REQUIRED_TOP_LEVEL_KEYS - balance.keys()
        assert not missing, f"Missing required top-level keys: {sorted(missing)}"


class TestBalanceSchema:
    """Each section of balance.yaml has the documented keys with correct types."""

    @pytest.fixture
    def balance(self) -> Mapping[str, object]:
        return load_balance()

    def test_time_section(self, balance: Mapping[str, object]) -> None:
        time = balance["time"]
        assert isinstance(time, dict)
        assert isinstance(time["seconds_per_tick"], float)
        assert isinstance(time["weeks_per_quarter"], int)
        assert isinstance(time["quarters_per_year"], int)

    def test_money_section(self, balance: Mapping[str, object]) -> None:
        money = balance["money"]
        assert isinstance(money, dict)
        assert isinstance(money["starting_cash"], int)
        assert money["starting_cash"] == 50_000
        assert isinstance(money["starting_debt"], int)
        assert isinstance(money["bankruptcy_cash_floor"], int)
        assert isinstance(money["salary_tier_multiplier"], float)
        assert isinstance(money["fire_severance_per_tier"], int)
        assert isinstance(money["target_revenue"], int)
        assert money["target_revenue"] == 200_000

    def test_departments_section(self, balance: Mapping[str, object]) -> None:
        deps = balance["departments"]
        assert isinstance(deps, dict)
        assert isinstance(deps["starting"], list)
        assert "Engineering" in deps["starting"]
        assert isinstance(deps["unlock_costs"], dict)
        assert isinstance(deps["max_employees_per_dept"], int)

    def test_employees_section(self, balance: Mapping[str, object]) -> None:
        emp = balance["employees"]
        assert isinstance(emp, dict)
        assert isinstance(emp["starting_count"], int)
        assert isinstance(emp["starting_skill_range"], list)
        assert len(emp["starting_skill_range"]) == 2
        assert isinstance(emp["max_skill"], int)
        assert isinstance(emp["promotion_cost"], int)
        assert isinstance(emp["demotion_savings"], int)
        assert isinstance(emp["zombie_satisfaction_threshold"], int)
        assert emp["zombie_satisfaction_threshold"] == 20

    def test_products_section(self, balance: Mapping[str, object]) -> None:
        prod = balance["products"]
        assert isinstance(prod, dict)
        assert isinstance(prod["starting"], list)
        assert isinstance(prod["lifecycle_weeks"], dict)
        assert isinstance(prod["revenue_per_skill_point_per_week"], (int, float))

    def test_competitors_section(self, balance: Mapping[str, object]) -> None:
        comp = balance["competitors"]
        assert isinstance(comp, dict)
        assert isinstance(comp["starting"], list)
        assert isinstance(comp["aggression_default"], float)
        assert isinstance(comp["max_aggression"], float)
        assert isinstance(comp["action_costs"], dict)
        assert "PRICE_CUT" in comp["action_costs"]
        assert "TALENT_POACH" in comp["action_costs"]
        assert "MARKETING_SPREE" in comp["action_costs"]
        assert comp["action_costs"]["MARKETING_SPREE"] == 1500
        assert isinstance(comp["poach_min_skill"], int)
        assert comp["poach_min_skill"] == 7

    def test_events_section(self, balance: Mapping[str, object]) -> None:
        ev = balance["events"]
        assert isinstance(ev, dict)
        assert isinstance(ev["random_event_per_tick_probability"], float)
        assert isinstance(ev["max_concurrent_chain_depth"], int)

    def test_endings_section(self, balance: Mapping[str, object]) -> None:
        end = balance["endings"]
        assert isinstance(end, dict)
        assert isinstance(end["ipo_market_cap_threshold"], int)
        assert isinstance(end["hostile_ma_trigger_competitor_aggression"], float)
        assert isinstance(end["voluntary_sale_min_cash"], int)
        assert isinstance(end["secret_conditions"], str)

    def test_save_section(self, balance: Mapping[str, object]) -> None:
        save = balance["save"]
        assert isinstance(save, dict)
        assert isinstance(save["autosave_every_n_ticks"], int)
        assert isinstance(save["max_backup_files"], int)


class TestMissingKeyBehavior:
    """QA scenario: removing a required key must fail the test (KeyError or AssertionError)."""

    def test_starting_cash_direct_access(self) -> None:
        """Given: balance.yaml is loaded
        When: starting_cash is accessed via the documented path
        Then: returns 50000 (raises KeyError if the key is removed, failing the test)
        """
        balance = load_balance()
        assert balance["money"]["starting_cash"] == 50_000

    def test_required_keys_set_contains_money(self) -> None:
        """Given: REQUIRED_TOP_LEVEL_KEYS is the contract
        When: a partial balance dict is missing money
        Then: money is reported as missing
        """
        partial: dict[str, object] = {
            "time": {"seconds_per_tick": 1.0, "weeks_per_quarter": 13, "quarters_per_year": 4},
        }
        missing = REQUIRED_TOP_LEVEL_KEYS - partial.keys()
        assert "money" in missing
