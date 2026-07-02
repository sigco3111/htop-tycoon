"""Korean internationalisation helpers and string dictionaries."""

from __future__ import annotations


def ko_label(en: str) -> str:
    """Return the Korean translation for a general label, or the key itself if unknown."""
    return _KO_GENERAL_LABELS.get(en, en)


def ko_money(cents: int) -> str:
    """Format cents as a Korean-style dollar string with comma separators."""
    sign = "-" if cents < 0 else ""
    abs_cents = abs(cents)
    dollars, remainder = divmod(abs_cents, 100)
    if remainder == 0:
        return f"{sign}${dollars:,}"
    return f"{sign}${dollars:,}.{remainder:02d}"


# ---------------------------------------------------------------------------
# General label translations
# ---------------------------------------------------------------------------

_KO_GENERAL_LABELS: dict[str, str] = {"Year": "년차"}

# ---------------------------------------------------------------------------
# Key-bindings
# ---------------------------------------------------------------------------

BINDINGS_KO: dict[str, str] = {
    "f1": "도움말",
    "f2": "저장",
    "f3": "검색",
    "f5": "트리",
    "f7": "승진",
    "f8": "로드",
    "f9": "해고",
}

# ---------------------------------------------------------------------------
# Strategy / setting labels
# ---------------------------------------------------------------------------

SET_KO_LABELS: dict[str, str] = {
    "AGGRESSIVE": "공격적",
    "CONSERVATIVE": "보수적",
    "BALANCED": "균형",
    "GENRE_FOCUS": "장르 집중",
}

# ---------------------------------------------------------------------------
# Job titles
# ---------------------------------------------------------------------------

JOB_KO: dict[str, str] = {
    "JUNIOR": "주니어",
    "SENIOR": "시니어",
    "LEAD": "리드",
    "ARTIST": "아티스트",
    "DESIGNER": "디자이너",
    "SOUND_ENGINEER": "사운드 엔지니어",
    "PRODUCER": "프로듀서",
    "QA": "QA",
}

# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

DEPT_KO: dict[str, str] = {
    "DEV": "개발",
    "ART": "아트",
    "SOUND": "사운드",
    "QA": "QA",
}

# ---------------------------------------------------------------------------
# Game genres
# ---------------------------------------------------------------------------

GENRE_KO: dict[str, str] = {
    "ACTION": "액션",
    "RPG": "RPG",
    "ADVENTURE": "어드벤처",
    "SIMULATION": "시뮬레이션",
    "PUZZLE": "퍼즐",
    "STRATEGY": "전략",
    "SPORTS": "스포츠",
    "HORROR": "호러",
    "CASUAL": "캐주얼",
}

# ---------------------------------------------------------------------------
# Strategy names (separate dict for clarity)
# ---------------------------------------------------------------------------

STRATEGY_KO: dict[str, str] = {
    "AGGRESSIVE": "공격적",
    "CONSERVATIVE": "보수적",
    "BALANCED": "균형",
    "GENRE_FOCUS": "장르 집중",
}

# ---------------------------------------------------------------------------
# Endings
# ---------------------------------------------------------------------------

ENDING_KO: dict[str, str] = {
    "BANKRUPTCY": "파산",
    "VOLUNTARY_SALE": "자발적 매각",
    "MEGA_HIT": "대박",
    "HALL_OF_FAME": "명예의 전당",
    "SECRET": "비밀",
}

ENDING_DESCRIPTIONS_KO: dict[str, str] = {
    "BANKRUPTCY": "회사가 파산하여 현금이 바닥나고 부채가 쌓였습니다.",
    "VOLUNTARY_SALE": "회사를 자발적으로 매각하여 새로운 시작을 합니다.",
    "MEGA_HIT": "단일 게임이 대박을 터뜨렸습니다!",
    "HALL_OF_FAME": "5개 이상의 게임이 명예의 전당에 올랐습니다!",
    "SECRET": "자사 콘솔 출시와 함께 메가히트를 달성했습니다!",
}

# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------

METRIC_KO: dict[str, str] = {
    "FUN": "재미",
    "GRAPHICS": "그래픽",
    "SOUND": "사운드",
    "ORIGINALITY": "독창성",
}

# ---------------------------------------------------------------------------
# Notification strings
# ---------------------------------------------------------------------------

NOTIFY_KO: dict[str, str] = {
    "saved": "저장됨",
    "loaded": "로드됨",
    "hired": "고용됨",
    "fired": "해고됨",
    "strategy_changed": "전략 변경",
}

STRATEGY_DESCRIPTION_KO: dict[str, str] = {
    "AGGRESSIVE": "공격적 고용, 큰 프로젝트, 위험 감수",
    "CONSERVATIVE": "신중, 현금 부족시 정리, 현금 비축",
    "BALANCED": "중간 규모 채용, 다양한 장르 혼합",
    "GENRE_FOCUS": "한 장르에 집중하여 깊이 개발",
}

EVENT_KIND_KO: dict[str, str] = {
    "hire": "고용",
    "fire": "해고",
    "start_project": "프로젝트 시작",
    "save_cash": "현금 비축",
    "boost_funding": "투자금 증가",
    "increase_funding": "투자금 증가",
    "ship": "출시",
    "bankruptcy": "파산",
    "voluntary_sale": "자발적 매각",
    "mega_hit": "대박",
    "purchase_console": "콘솔 구매",
    "release": "출시",
}
