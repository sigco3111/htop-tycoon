"""S7 RED: i18n module — ko_label, ko_money, and all Korean string dictionaries."""

from __future__ import annotations

from htop_tycoon.ui.i18n import (
    BINDINGS_KO,
    DEPT_KO,
    ENDING_DESCRIPTIONS_KO,
    ENDING_KO,
    GENRE_KO,
    JOB_KO,
    METRIC_KO,
    NOTIFY_KO,
    SET_KO_LABELS,
    STRATEGY_KO,
    ko_label,
    ko_money,
)


class TestKoLabel:
    def test_ko_label_known_key_year(self) -> None:
        result = ko_label("Year")
        assert isinstance(result, str)
        assert result == "년차"

    def test_ko_label_unknown_key_fallback_returns_key(self) -> None:
        result = ko_label("NonExistentKey")
        assert result == "NonExistentKey"

    def test_ko_label_fallback_is_idempotent(self) -> None:
        key = "AlsoNonExistent"
        assert ko_label(key) == key
        assert ko_label(key) == key


class TestKoMoney:
    """ko_money accepts integer cents (Money.cents semantics) and formats as $-string.

    Standard cents convention: 100 cents = $1. 12345 cents = $123.45.
    """

    def test_ko_money_one_hundred_dollars(self) -> None:
        result = ko_money(100_00)
        assert result == "$100"

    def test_ko_money_negative_fifty_thousand_dollars(self) -> None:
        result = ko_money(-50_000_00)
        assert result == "-$50,000"

    def test_ko_money_with_cents_remainder(self) -> None:
        result = ko_money(123_45)
        assert result == "$123.45"

    def test_ko_money_zero(self) -> None:
        result = ko_money(0)
        assert result == "$0"

    def test_ko_money_negative_fifty_dollars(self) -> None:
        result = ko_money(-50_00)
        assert result == "-$50"


class TestBindingsKo:
    def test_bindings_ko_f1(self) -> None:
        assert BINDINGS_KO["f1"] == "도움말"

    def test_bindings_ko_f2(self) -> None:
        assert BINDINGS_KO["f2"] == "저장"

    def test_bindings_ko_f3(self) -> None:
        assert BINDINGS_KO["f3"] == "검색"

    def test_bindings_ko_f5(self) -> None:
        assert BINDINGS_KO["f5"] == "트리"

    def test_bindings_ko_f7(self) -> None:
        assert BINDINGS_KO["f7"] == "승진"

    def test_bindings_ko_f8(self) -> None:
        assert BINDINGS_KO["f8"] == "로드"

    def test_bindings_ko_f9(self) -> None:
        assert BINDINGS_KO["f9"] == "해고"


class TestSetKoLabels:
    def test_set_ko_labels_aggressive(self) -> None:
        assert SET_KO_LABELS["AGGRESSIVE"] == "공격적"

    def test_set_ko_labels_conservative(self) -> None:
        assert SET_KO_LABELS["CONSERVATIVE"] == "보수적"

    def test_set_ko_labels_balanced(self) -> None:
        assert SET_KO_LABELS["BALANCED"] == "균형"

    def test_set_ko_labels_genre_focus(self) -> None:
        assert SET_KO_LABELS["GENRE_FOCUS"] == "장르 집중"


class TestJobKo:
    def test_job_ko_junior(self) -> None:
        assert JOB_KO["JUNIOR"] == "주니어"

    def test_job_ko_senior(self) -> None:
        assert JOB_KO["SENIOR"] == "시니어"

    def test_job_ko_lead(self) -> None:
        assert JOB_KO["LEAD"] == "리드"

    def test_job_ko_artist(self) -> None:
        assert JOB_KO["ARTIST"] == "아티스트"

    def test_job_ko_designer(self) -> None:
        assert JOB_KO["DESIGNER"] == "디자이너"

    def test_job_ko_sound_engineer(self) -> None:
        assert JOB_KO["SOUND_ENGINEER"] == "사운드 엔지니어"

    def test_job_ko_producer(self) -> None:
        assert JOB_KO["PRODUCER"] == "프로듀서"

    def test_job_ko_qa(self) -> None:
        assert JOB_KO["QA"] == "QA"


class TestDeptKo:
    def test_dept_ko_dev(self) -> None:
        assert DEPT_KO["DEV"] == "개발"

    def test_dept_ko_art(self) -> None:
        assert DEPT_KO["ART"] == "아트"

    def test_dept_ko_sound(self) -> None:
        assert DEPT_KO["SOUND"] == "사운드"

    def test_dept_ko_qa(self) -> None:
        assert DEPT_KO["QA"] == "QA"


class TestGenreKo:
    def test_genre_ko_action(self) -> None:
        assert GENRE_KO["ACTION"] == "액션"

    def test_genre_ko_rpg(self) -> None:
        assert GENRE_KO["RPG"] == "RPG"

    def test_genre_ko_adventure(self) -> None:
        assert GENRE_KO["ADVENTURE"] == "어드벤처"

    def test_genre_ko_simulation(self) -> None:
        assert GENRE_KO["SIMULATION"] == "시뮬레이션"

    def test_genre_ko_puzzle(self) -> None:
        assert GENRE_KO["PUZZLE"] == "퍼즐"

    def test_genre_ko_strategy(self) -> None:
        assert GENRE_KO["STRATEGY"] == "전략"

    def test_genre_ko_sports(self) -> None:
        assert GENRE_KO["SPORTS"] == "스포츠"

    def test_genre_ko_horror(self) -> None:
        assert GENRE_KO["HORROR"] == "호러"

    def test_genre_ko_casual(self) -> None:
        assert GENRE_KO["CASUAL"] == "캐주얼"


class TestStrategyKo:
    def test_strategy_ko_aggressive(self) -> None:
        assert STRATEGY_KO["AGGRESSIVE"] == "공격적"

    def test_strategy_ko_conservative(self) -> None:
        assert STRATEGY_KO["CONSERVATIVE"] == "보수적"

    def test_strategy_ko_balanced(self) -> None:
        assert STRATEGY_KO["BALANCED"] == "균형"

    def test_strategy_ko_genre_focus(self) -> None:
        assert STRATEGY_KO["GENRE_FOCUS"] == "장르 집중"


class TestEndingKo:
    def test_ending_ko_bankruptcy(self) -> None:
        assert ENDING_KO["BANKRUPTCY"] == "파산"

    def test_ending_ko_voluntary_sale(self) -> None:
        assert ENDING_KO["VOLUNTARY_SALE"] == "자발적 매각"

    def test_ending_ko_mega_hit(self) -> None:
        assert ENDING_KO["MEGA_HIT"] == "대박"

    def test_ending_ko_hall_of_fame(self) -> None:
        assert ENDING_KO["HALL_OF_FAME"] == "명예의 전당"

    def test_ending_ko_secret(self) -> None:
        assert ENDING_KO["SECRET"] == "비밀"


class TestEndingDescriptionsKo:
    def test_ending_descriptions_ko_bankruptcy_non_empty(self) -> None:
        desc = ENDING_DESCRIPTIONS_KO["BANKRUPTCY"]
        assert isinstance(desc, str)
        assert len(desc) > 0
        assert "파산" in desc or "현금" in desc or "부채" in desc


class TestMetricKo:
    def test_metric_ko_fun(self) -> None:
        assert METRIC_KO["FUN"] == "재미"

    def test_metric_ko_graphics(self) -> None:
        assert METRIC_KO["GRAPHICS"] == "그래픽"

    def test_metric_ko_sound(self) -> None:
        assert METRIC_KO["SOUND"] == "사운드"

    def test_metric_ko_originality(self) -> None:
        assert METRIC_KO["ORIGINALITY"] == "독창성"


class TestNotifyKo:
    def test_notify_ko_saved(self) -> None:
        assert NOTIFY_KO["saved"] == "저장됨"

    def test_notify_ko_loaded(self) -> None:
        assert NOTIFY_KO["loaded"] == "로드됨"

    def test_notify_ko_hired(self) -> None:
        assert NOTIFY_KO["hired"] == "고용됨"

    def test_notify_ko_fired(self) -> None:
        assert NOTIFY_KO["fired"] == "해고됨"

    def test_notify_ko_strategy_changed(self) -> None:
        assert NOTIFY_KO["strategy_changed"] == "전략 변경"
