"""Tests for T8a: endings.yaml — 5 Korean ending flavor texts + summary stat labels.

Locks the contract from .omo/plans/htop-tycoon.md line 282-315:
- load_endings() returns a dict with EXACTLY 5 keys.
- The 5 keys are BANKRUPTCY, IPO, HOSTILE_MA, VOLUNTARY_SALE, SECRET.
- Each entry has title_ko, summary_ko, stats_labels (Korean label per stat key).
- The SECRET entry's flavor text (title_ko + summary_ko + stats_labels values)
  contains NO spoilers: must not literally mention "max_skill", "10",
  "max tier", or "all departments" — those trigger conditions live in
  domain/ending.py (T8) and engine/ending.py (T15).
- load_endings() is identity-cached via functools.lru_cache (mirror load_balance).

QA scenarios from the plan:
- happy: load endings.yaml -> assert 5 endings, each with title_ko and summary_ko.
- failure: remove SECRET entry -> reload -> assert KeyError (tested indirectly
  via the structural assertions below; modifying the package file in a test
  would mutate shipped state, so the structural assertion is the equivalent
  observable failure mode).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from htop_tycoon.data import load_endings

if TYPE_CHECKING:
    from collections.abc import Mapping


REQUIRED_KEYS: frozenset[str] = frozenset(
    {"BANKRUPTCY", "IPO", "HOSTILE_MA", "VOLUNTARY_SALE", "SECRET"}
)

# Spoiler terms that must NEVER appear in SECRET flavor text. These describe
# the SECRET trigger condition; revealing them in UI copy would defeat the
# mystery. The contract per AGENTS.md "CRITICAL INVARIANTS": SECRET condition
# is all_depts_unlocked AND all_employees_skill == max_skill AND
# secret_investor_cleared. The flavor text must reference none of that.
SECRET_SPOILER_TERMS: tuple[str, ...] = (
    "max_skill",
    "10",
    "max tier",
    "all departments",
)


class TestLoadEndingsHelper:
    """load_endings() returns parsed YAML and is cached after first call."""

    def test_returns_dict(self) -> None:
        """Given: load_endings() is callable
        When: called
        Then: returns a dict
        """
        result = load_endings()
        assert isinstance(result, dict)

    def test_returns_exactly_five_keys(self) -> None:
        """Given: load_endings() is callable
        When: called
        Then: returns exactly 5 keys (no more, no less)
        """
        result = load_endings()
        assert len(result) == 5, (
            f"Expected exactly 5 endings, got {len(result)}: {sorted(result.keys())}"
        )

    def test_cached_returns_same_object(self) -> None:
        """Given: load_endings has been called once
        When: called again
        Then: returns the exact same object (lru_cache identity)
        """
        first = load_endings()
        second = load_endings()
        assert first is second


class TestEndingsSchema:
    """Each of the 5 endings has the documented Korean fields."""

    @pytest.fixture
    def endings(self) -> Mapping[str, object]:
        return load_endings()

    def test_all_required_keys_present(self, endings: Mapping[str, object]) -> None:
        """Given: a valid endings.yaml
        When: load_endings() is called
        Then: every required ending key is present
        """
        missing = REQUIRED_KEYS - endings.keys()
        assert not missing, f"Missing required ending keys: {sorted(missing)}"

    def test_no_extra_keys(self, endings: Mapping[str, object]) -> None:
        """Given: the endings.yaml contract defines exactly 5 endings
        When: load_endings() is called
        Then: no extra ending keys sneak in
        """
        extra = endings.keys() - REQUIRED_KEYS
        assert not extra, f"Unexpected extra ending keys: {sorted(extra)}"

    @pytest.mark.parametrize("ending_key", sorted(REQUIRED_KEYS))
    def test_each_entry_has_title_ko(
        self, endings: Mapping[str, object], ending_key: str
    ) -> None:
        """Given: each ending entry
        When: accessed by key
        Then: has a non-empty Korean title_ko string
        """
        entry = endings[ending_key]
        assert isinstance(entry, dict), f"{ending_key} entry must be a mapping"
        assert "title_ko" in entry, f"{ending_key} missing title_ko"
        title = entry["title_ko"]
        assert isinstance(title, str), f"{ending_key}.title_ko must be a string"
        assert title.strip(), f"{ending_key}.title_ko must be non-empty"

    @pytest.mark.parametrize("ending_key", sorted(REQUIRED_KEYS))
    def test_each_entry_has_summary_ko(
        self, endings: Mapping[str, object], ending_key: str
    ) -> None:
        """Given: each ending entry
        When: accessed by key
        Then: has a non-empty Korean summary_ko string
        """
        entry = endings[ending_key]
        assert "summary_ko" in entry, f"{ending_key} missing summary_ko"
        summary = entry["summary_ko"]
        assert isinstance(summary, str), f"{ending_key}.summary_ko must be a string"
        assert summary.strip(), f"{ending_key}.summary_ko must be non-empty"

    @pytest.mark.parametrize("ending_key", sorted(REQUIRED_KEYS))
    def test_each_entry_has_stats_labels(
        self, endings: Mapping[str, object], ending_key: str
    ) -> None:
        """Given: each ending entry
        When: accessed by key
        Then: has a non-empty stats_labels mapping of stat_key -> Korean label
        """
        entry = endings[ending_key]
        assert "stats_labels" in entry, f"{ending_key} missing stats_labels"
        labels = entry["stats_labels"]
        assert isinstance(labels, dict), f"{ending_key}.stats_labels must be a mapping"
        assert labels, f"{ending_key}.stats_labels must be non-empty"
        for stat_key, label in labels.items():
            assert isinstance(stat_key, str), (
                f"{ending_key}.stats_labels keys must be strings"
            )
            assert isinstance(label, str), (
                f"{ending_key}.stats_labels[{stat_key!r}] must be a string"
            )
            assert label.strip(), (
                f"{ending_key}.stats_labels[{stat_key!r}] must be non-empty"
            )


class TestSecretEndingHasNoSpoilers:
    """SECRET flavor text must not leak trigger conditions.

    AGENTS.md "CRITICAL INVARIANTS" pins SECRET condition as
    all_depts_unlocked AND all_employees_skill == max_skill AND
    secret_investor_cleared. Any flavor-text reference to that would
    spoil the mystery. This test enforces the contract.
    """

    @pytest.fixture
    def secret_text(self) -> str:
        """Concatenate all SECRET flavor text fields into a single string."""
        endings = load_endings()
        entry = endings["SECRET"]
        parts: list[str] = [
            str(entry["title_ko"]),
            str(entry["summary_ko"]),
        ]
        for label in entry["stats_labels"].values():
            parts.append(str(label))
        return "\n".join(parts)

    @pytest.mark.parametrize("spoiler", SECRET_SPOILER_TERMS)
    def test_secret_text_omits_spoiler_term(
        self, secret_text: str, spoiler: str
    ) -> None:
        """Given: SECRET flavor text (title_ko + summary_ko + stats_labels values)
        When: scanned for a known spoiler term
        Then: the term is not present
        """
        assert spoiler not in secret_text, (
            f"SECRET flavor text leaks spoiler {spoiler!r}; "
            f"must not reveal trigger conditions. Full text:\n{secret_text}"
        )


class TestExactKoreanCopy:
    """Pin the exact Korean title_ko values from .omo/plans/htop-tycoon.md.

    These are the user-visible titles. If any change is needed, the plan must
    be updated first (AGENTS.md "CRITICAL INVARIANTS": balance/content lives
    in data files, not code, and changes require plan updates).
    """

    EXPECTED_TITLE_KO: dict[str, str] = {
        "BANKRUPTCY": "파산",
        "IPO": "상장 성공",
        "HOSTILE_MA": "적대적 인수",
        "VOLUNTARY_SALE": "자발적 매각",
        "SECRET": "비밀 엔딩",
    }

    def test_titles_match_plan_exactly(self) -> None:
        """Given: the expected title_ko per ending from the plan
        When: load_endings() is called
        Then: every title_ko matches exactly
        """
        endings = load_endings()
        for key, expected_title in self.EXPECTED_TITLE_KO.items():
            actual_title = endings[key]["title_ko"]
            assert actual_title == expected_title, (
                f"{key}.title_ko mismatch: "
                f"expected {expected_title!r}, got {actual_title!r}"
            )
