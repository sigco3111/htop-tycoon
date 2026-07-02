"""Phase 2H pilot tests for 4 new screen modules: Help, Search, NewProject, Promote.

RED state — these screens are not yet implemented. Each test documents the
expected Korean labels so production code can match them.

EXPECTED_TRANSLATIONS maps English concepts to Korean strings used in assertions.
"""

from __future__ import annotations

from htop_tycoon.domain.enums import Genre
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.help import render_help_text
from htop_tycoon.ui.screens.new_project import render_new_project_text
from htop_tycoon.ui.screens.promote import render_promote_text
from htop_tycoon.ui.screens.search import render_search_text

#: Expected Korean labels derived from README.md key-bindings table and
#: ending/strategy sections. Production code should use these exact strings.
EXPECTED_TRANSLATIONS = {
    # F-key labels (footer hints)
    "F1_help": "도움말",
    "F2_save": "저장",
    "F3_search": "검색",
    "F5_tree": "트리",
    "F7_promote": "승진",
    "F8_load": "로드",
    "F9_fire": "해고",
    "F10_sell": "매각",
    # Strategy names
    "aggressive": "공격적",
    "conservative": "보수적",
    "balanced": "균형",
    "genre_focus": "장르 집중",
    # Ending names
    "bankruptcy": "파산",
    "mega_hit": "대박",
    "hall_of_fame": "명예의 전당",
    # Speed controls
    "speed_1x": "1x",
    "pause": "정지",
    "pause_alt": "일시정지",
    # Search screen
    "search_prompt": "검색:",
    "search_prompt_alt": "이름 입력:",
    # New project screen
    "select_genre": "장르 선택",
    # Promote screen
    "promote_header": "승진",
    "can_promote": "가능",
    "pick_instruction": "1-N 선택",
}


# ---------------------------------------------------------------------------
# HelpScreen
# ---------------------------------------------------------------------------


def test_help_screen_renders_all_f_keys() -> None:
    """HelpScreen renders Korean F-key labels: F1 도움말, F2 저장, F3 검색,
    F5 트리, F7 승진, F8 로드, F9 해고, F10 매각."""
    text = render_help_text()
    assert EXPECTED_TRANSLATIONS["F1_help"] in text
    assert EXPECTED_TRANSLATIONS["F2_save"] in text
    assert EXPECTED_TRANSLATIONS["F3_search"] in text
    assert EXPECTED_TRANSLATIONS["F5_tree"] in text
    assert EXPECTED_TRANSLATIONS["F7_promote"] in text
    assert EXPECTED_TRANSLATIONS["F8_load"] in text
    assert EXPECTED_TRANSLATIONS["F9_fire"] in text
    assert EXPECTED_TRANSLATIONS["F10_sell"] in text


def test_help_screen_renders_all_four_strategies() -> None:
    """HelpScreen lists all 4 strategy names in Korean."""
    text = render_help_text()
    assert EXPECTED_TRANSLATIONS["aggressive"] in text
    assert EXPECTED_TRANSLATIONS["conservative"] in text
    assert EXPECTED_TRANSLATIONS["balanced"] in text
    assert EXPECTED_TRANSLATIONS["genre_focus"] in text


def test_help_screen_renders_ending_names() -> None:
    """HelpScreen lists at least 3 Korean ending names: 파산, 대박, 명예의 전당."""
    text = render_help_text()
    assert EXPECTED_TRANSLATIONS["bankruptcy"] in text
    assert EXPECTED_TRANSLATIONS["mega_hit"] in text
    assert EXPECTED_TRANSLATIONS["hall_of_fame"] in text


def test_help_screen_renders_speed_hints() -> None:
    """HelpScreen includes speed-control hints: 1x, 정지, or 일시정지."""
    text = render_help_text()
    speed_hints = [
        EXPECTED_TRANSLATIONS["speed_1x"],
        EXPECTED_TRANSLATIONS["pause"],
        EXPECTED_TRANSLATIONS["pause_alt"],
    ]
    assert any(hint in text for hint in speed_hints)


# ---------------------------------------------------------------------------
# SearchScreen
# ---------------------------------------------------------------------------


def test_search_screen_renders_query_prompt() -> None:
    """SearchScreen displays a Korean query prompt like '검색:' or '이름 입력:'."""
    text = render_search_text("A", ["Alice", "Bob"])
    assert EXPECTED_TRANSLATIONS["search_prompt"] in text or EXPECTED_TRANSLATIONS["search_prompt_alt"] in text


def test_search_screen_renders_candidates() -> None:
    """SearchScreen renders candidate names (case-insensitive substring match)."""
    text = render_search_text("A", ["Alice", "Bob"])
    assert "Alice" in text or "alice" in text.lower()
    assert "Bob" in text or "bob" in text.lower()


def test_search_screen_renders_empty_candidates() -> None:
    """SearchScreen handles empty candidate list without crashing."""
    text = render_search_text("X", [])
    assert isinstance(text, str)


# ---------------------------------------------------------------------------
# NewProjectScreen
# ---------------------------------------------------------------------------


def test_new_project_screen_renders_all_genres_in_korean() -> None:
    """NewProjectScreen renders ALL provided genres in Korean using GENRE_KO mapping."""
    text = render_new_project_text([Genre.RPG, Genre.ACTION])
    genre_ko_map = {
        Genre.ACTION: "액션",
        Genre.RPG: "RPG",
        Genre.ADVENTURE: "어드벤처",
        Genre.SIMULATION: "시뮬레이션",
        Genre.PUZZLE: "퍼즐",
        Genre.STRATEGY: "전략",
        Genre.SPORTS: "스포츠",
        Genre.HORROR: "호러",
        Genre.CASUAL: "캐주얼",
    }
    for genre in [Genre.RPG, Genre.ACTION]:
        assert genre_ko_map[genre] in text, f"{genre.value} not found in: {text}"


def test_new_project_screen_renders_genre_selection_prompt() -> None:
    """NewProjectScreen includes '장르 선택' prompt."""
    text = render_new_project_text([Genre.RPG])
    assert EXPECTED_TRANSLATIONS["select_genre"] in text


def test_new_project_screen_renders_single_genre() -> None:
    """NewProjectScreen renders correctly with a single genre."""
    text = render_new_project_text([Genre.STRATEGY])
    assert isinstance(text, str)
    assert len(text) > 0


# ---------------------------------------------------------------------------
# PromoteScreen
# ---------------------------------------------------------------------------


def test_promote_screen_renders_promote_header() -> None:
    """PromoteScreen shows '승진' header."""
    state = mock_state(speed=0)
    text = render_promote_text(state)
    assert EXPECTED_TRANSLATIONS["promote_header"] in text


def test_promote_screen_marks_promotable_employee() -> None:
    """PromoteScreen marks Ada (LEAD L5 sat 85) with '가능' or '✓' marker."""
    state = mock_state(speed=0)
    text = render_promote_text(state)
    assert "Ada" in text
    markers = [EXPECTED_TRANSLATIONS["can_promote"], "✓"]
    assert any(m in text for m in markers), f"None of {markers} found for Ada in: {text}"


def test_promote_screen_lists_only_leads() -> None:
    """PromoteScreen only lists LEAD employees (promotion target)."""
    state = mock_state(speed=0)
    text = render_promote_text(state)
    assert "Ada" in text
    assert "Bob" not in text
    assert "Eve" not in text


def test_promote_screen_renders_selection_instruction() -> None:
    """PromoteScreen shows '1-N 선택' (or similar) instruction."""
    state = mock_state(speed=0)
    text = render_promote_text(state)
    assert EXPECTED_TRANSLATIONS["pick_instruction"] in text or "선택" in text
