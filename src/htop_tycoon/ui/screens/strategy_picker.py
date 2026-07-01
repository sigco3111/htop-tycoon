"""htop-tycoon v3.0 — StrategyPickerScreen (spec §4.1).

Modal that lets the player pick one of the 4 strategies (spec §3.1):
- Aggressive    — auto-hire > 30K, no fire, immediate game starts, high-risk
- Conservative  — auto-hire > 100K, fire low performers, heavy training, safe
- Balanced      — auto-hire > 50K, fire very low, moderate, mix
- Genre Focus   — spam one genre for combo bonuses

Spec §4.1: key ``s`` opens the picker. The selection is stored on
``app.active_strategy`` so the header / AI behavior can pick it up.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from htop_tycoon.engine.strategy import register_default_strategies

# Spec §3.1: the 4 strategy names. The Registry uses these keys.
STRATEGY_NAMES: tuple[str, ...] = ("balanced", "aggressive", "conservative", "genre_focus")
STRATEGY_KO: dict[str, str] = {
    "balanced": "균형 (Balanced)",
    "aggressive": "공격적 (Aggressive)",
    "conservative": "보수적 (Conservative)",
    "genre_focus": "장르 특화 (Genre Focus)",
}
STRATEGY_DESC: dict[str, str] = {
    "balanced": "hire > 50K / fire very low / moderate train / mix safe+risky",
    "aggressive": "hire > 30K / no fire / immediate start / high-risk-high-reward",
    "conservative": "hire > 100K / fire low performers / heavy train / safe only",
    "genre_focus": "spam chosen genre for combo bonuses",
}


class StrategyPickerScreen(ModalScreen[str | None]):
    """Spec §4.1: 's → StrategyPickerScreen shows 4 options'."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "취소"),
    ]

    DEFAULT_CSS = """
    StrategyPickerScreen {
        align: center middle;
    }
    #strategy-picker {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        register_default_strategies()  # idempotent
        with Vertical(id="strategy-picker"):
            yield Static("[bold]전략 선택 (Strategy Picker)[/]", id="title")
            yield Static("자동 모드를 위한 전략을 선택하세요.\n(Spec §3.1)", id="subtitle")
            for name in STRATEGY_NAMES:
                yield Button(
                    f"{STRATEGY_KO[name]}",
                    id=f"btn-{name}",
                )
            yield Static("", id="description")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Pick the strategy and dismiss.

        Also updates ``app.active_strategy`` so the header / AI behavior
        can pick up the selection (spec §3.3: 'Auto toggle key d; Strategy
        picker key s').
        """
        button_id = event.button.id
        if button_id is None:
            self.dismiss(None)
            return
        name = button_id.removeprefix("btn-")
        if name in STRATEGY_NAMES:
            self.app.active_strategy = name  # type: ignore[attr-defined]
            self.dismiss(name)
        else:
            self.dismiss(None)

    async def action_dismiss(self, value: str | None = None) -> None:
        self.dismiss(value)


__all__ = ["StrategyPickerScreen"]
