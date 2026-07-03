"""EndingScreen (modal) + LegacyPanel (body widget) — Korean localization."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.domain.money import Money
from htop_tycoon.engine.endings import (
    ENDING_DESCRIPTIONS,
    ENDING_LABELS,
    Ending,
    EndingKind,
    LegacyScore,
)
from htop_tycoon.ui.i18n import ENDING_KO
from htop_tycoon.ui.i18n import bind_en_ko

__all__ = [
    "EndingScreen",
    "LegacyPanel",
    "ENDING_LABELS",
    "ENDING_DESCRIPTIONS",
]


def render_legacy_line(score: LegacyScore) -> str:
    cash = Money(score.ending_cash_cents)
    kind_ko = ENDING_KO.get(score.ending_kind.value, score.ending_kind.value)
    return (
        f"{kind_ko} · {score.ending_year}년차 · "
        f"자금 {cash} · 팬 {score.total_fans:,}명 · "
        f"출시 {score.games_shipped}개 · 메가히트 {score.mega_hits}개"
    )


class LegacyPanel:
    """Body widget showing all-time legacy scores (not a modal)."""

    __slots__ = ("_scores",)

    def __init__(self, scores: tuple[LegacyScore, ...] | list[LegacyScore]) -> None:
        self._scores: tuple[LegacyScore, ...] = tuple(scores)

    @property
    def scores(self) -> tuple[LegacyScore, ...]:
        return self._scores

    def render(self) -> str:
        if not self._scores:
            return "레거시 (아직 엔딩 없음)"
        lines = [f"레거시 ({len(self._scores)})"]
        for score in self._scores:
            lines.append(f"  {render_legacy_line(score)}")
        return "\n".join(lines)


def render_ending_text(ending: Ending, legacy: LegacyScore) -> str:
    """Pure function returning EndingScreen body Korean text."""
    label = ENDING_KO.get(ending.kind.value, ending.kind.value)
    cash = Money(legacy.ending_cash_cents)
    return (
        f"=== {label} ===\n"
        f"{legacy.ending_year}년차\n"
        f"자금: {cash}\n"
        f"팬: {legacy.total_fans:,}명\n"
        f"출시 게임: {legacy.games_shipped}개\n"
        f"메가히트: {legacy.mega_hits}개\n"
        f"\n{ending.description}\n"
        f"\n[새 게임]    [종료]"
    )


class EndingScreen(ModalScreen[None]):
    """엔딩 모달. Esc로 닫기."""

    BINDINGS = [
        *bind_en_ko("escape", "app.close_top_modal", "닫기", show=True),
        *bind_en_ko("0", "app.digit('0')", "정지", show=True),
        *bind_en_ko("1", "app.digit('1')", "1x", show=True),
        *bind_en_ko("2", "app.digit('2')", "2x", show=True),
        *bind_en_ko("3", "app.digit('3')", "3x", show=True),
        *bind_en_ko("4", "app.digit('4')", "4x", show=True),
    ]

    DEFAULT_CSS = """
    EndingScreen {
        layer: modal;
        align: center middle;
    }
    #ending-content {
        width: 70;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def __init__(self, ending: Ending, legacy: LegacyScore) -> None:
        super().__init__()
        self._ending = ending
        self._legacy = legacy

    @property
    def ending(self) -> Ending:
        return self._ending

    @property
    def legacy(self) -> LegacyScore:
        return self._legacy

    def compose(self) -> ComposeResult:
        yield Static(
            render_ending_text(self._ending, self._legacy),
            id="ending-content",
        )


ENDING_KIND_LABELS = ENDING_LABELS
ENDING_KIND_DESCRIPTIONS = ENDING_DESCRIPTIONS
ENDING_VALUES: tuple[str, ...] = tuple(k.value for k in EndingKind)

