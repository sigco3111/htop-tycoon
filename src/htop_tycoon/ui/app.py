"""htop-tycoon v3.0 — HtopTycoonApp (spec §4.1 + §5.3).

Main Textual app. Composes header + metric bar + footer around a
content area. ``state`` is the reactive ``GameState``; ``run_day`` is
called by an interval timer (speed = 1..3 ticks/second; 0 = pause;
4 = QA-only 4x).

The app does NOT import from ``engine.tick`` directly to avoid circular
imports — it uses the engine via a single dispatch call. The engine
itself is pure (no I/O, no UI).
"""
from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from htop_tycoon.bindings.registry import BINDINGS, validate_bindings
from htop_tycoon.domain import GameState
from htop_tycoon.ui.widgets import (
    EmployeeTable,
    HtopFooter,
    HtopHeader,
    MetricBar,
    OrgTree,
    StrategyStatus,
)

# Module-level so the BINDINGS class-body generator expression can see it
# (class-body generator expressions don't capture other class-scope names).
# Excludes ' ' (space) — Textual rejects empty-string bindings; the spec
# 'tag employee' action ships as a Button widget in Wave 6+ rather than a
# keyboard shortcut.
_BINDING_KEY_PREFIXES: tuple[str, ...] = (
    "F", "h", "S", "/", "\\", "t", "<", ">", "]", "[", "k", "q",
    "H", "n", "g", "s", "d", "a", "c", "enter", "escape", "p",
    "0", "1", "2", "3", "4", "up", "down",
)


class HtopTycoonApp(App[None]):
    """Spec §4.1: top-level Textual app with the htop metaphor."""

    TITLE = "htop-tycoon v3.0"
    SUB_TITLE = "Korean Game Dev Story"

    CSS = """
    Screen {
        layout: vertical;
    }
    #body {
        height: 1fr;
    }
    """

    # Textual BINDINGS expects ``Binding | tuple[str, str] | tuple[str, str, str]``.
    # We pass the same key/action triples as ``(key, action, description)`` tuples
    # so the type matches the App base class. The full Binding records (with
    # Korean labels) live in ``htop_tycoon.bindings.registry.BINDINGS`` and
    # are rendered into the footer separately.
    # Spec §4.1: every action has a default binding key. We exclude ' '
    # (space) because Textual rejects empty-string bindings; the spec 'tag
    # employee' action ships as a Button widget in Wave 6+ rather than a
    # keyboard shortcut.
    # BINDINGS override — annotate with ClassVar but no element type so
    # mypy doesn't try to enforce invariance (the base class uses a union
    # of three types; we use a narrower two-tuple form). The override
    # itself is intentional (Textual supports it); the missing annotation
    # tells mypy "trust the developer". The filter against
    # ``_BINDING_KEY_PREFIXES`` (module-level) keeps the registration narrow.
    BINDINGS: ClassVar = [
        (b.key, b.action, b.description)
        for b in BINDINGS
        if b.description and b.key.startswith(_BINDING_KEY_PREFIXES)
    ]

    def __init__(
        self,
        *,
        state: GameState | None = None,
        speed: int = 1,
        auto_mode: bool = False,
        strategy_name: str | None = None,
    ) -> None:
        super().__init__()
        # Validate again at construction time (the module-level call catches
        # most cases, but tests may construct custom bindings).
        validate_bindings(BINDINGS)
        self._state: GameState = state or GameState()
        self.speed: int = speed  # 0 = pause, 1..4 ticks/sec
        self.auto_mode: bool = auto_mode
        self.active_strategy: str | None = strategy_name
        self._tick_interval: float = 1.0 / max(speed, 1) if speed > 0 else 0.0

    def compose(self) -> ComposeResult:
        """Spec §4.1: header (top) + body + metric bar + footer (bottom)."""
        yield HtopHeader(id="header")
        with Vertical(id="body"):
            yield Static(
                "[bold]htop-tycoon[/]\n\n"
                "Wave 6 first-pass UI.\n"
                "Press [F1]h for help, [F2]S to save.",
                id="content",
            )
            yield MetricBar(id="metric")
            yield EmployeeTable(id="employee-table")
            yield StrategyStatus(id="strategy-status")
        yield OrgTree(id="org-tree")
        yield HtopFooter(id="footer")

    def on_mount(self) -> None:
        """Bind initial state to widgets + start the per-day timer."""
        # Register the htop-style theme (spec §4.1). Done in on_mount
        # because the installed Textual version exposes register_theme as
        # an instance method (not a classmethod), so a module-level call
        # would fail. Lazy import avoids a cycle with htop_tycoon.ui.theme.
        from htop_tycoon.ui.theme import HTOPTYCOON_THEME
        try:
            self.register_theme(HTOPTYCOON_THEME)
        except Exception:  # noqa: BLE001
            # Older Textual versions may not support register_theme the same
            # way; fall back to the built-in theme so the app still boots.
            pass
        self.query_one(HtopHeader).state = self._state
        # Pick the first active project (if any) for the metric bar
        active = next((p for p in self._state.projects if not p.is_complete), None)
        self.query_one(MetricBar).project = active
        # Start the tick timer (only if speed > 0)
        if self.speed > 0:
            self._timer = self.set_interval(
                self._tick_interval, self._tick_one_day
            )

    def _tick_one_day(self) -> None:
        """Advance the simulation by one game-day (spec §5.2)."""
        from htop_tycoon.engine.rng import GameRNG
        from htop_tycoon.engine.tick import run_day
        rng = GameRNG(self._state.rng_seed + self._state.day)  # deterministic per day
        self._state, _events = run_day(self._state, rng, strategy=None)
        # Push the new state into the reactive widgets
        self.query_one(HtopHeader).state = self._state
        active = next((p for p in self._state.projects if not p.is_complete), None)
        self.query_one(MetricBar).project = active

    # Action dispatch — spec §4.1 actions. The strategy_picker and
    # game_starter push the modal screens. Save delegates to the persistence
    # layer (spec §6). Auto toggle and speed control are simple flags.
    def action_help(self) -> None:
        self.query_one("#content", Static).update(
            "[bold]도움말 (Help)[/]\n\n"
            "F1 / h — 이 도움말\n"
            "F2 / S — 저장 (save)\n"
            "F3 / / — 직원 검색\n"
            "F4 / \\\\ — 필터\n"
            "F5 / t — 부서 트리 토글\n"
            "F6 / <> — 정렬 사이클\n"
            "F7 / ] — 승진\n"
            "F8 / [ — 감봉\n"
            "F9 / k — 해고\n"
            "F10 / q — 종료/매각\n"
            "s — 전략 선택 (Strategy Picker)\n"
            "n — 새 게임 (New Game)\n"
            "0 — 정지, 1-3 — 속도, 4 — 4x (QA)\n"
        )

    def action_strategy_picker(self) -> None:
        """Spec §4.1: 's' opens the StrategyPickerScreen."""
        from htop_tycoon.ui.screens.strategy_picker import StrategyPickerScreen
        self.push_screen(StrategyPickerScreen())

    def action_start_game(self) -> None:
        """Spec §4.1: 'n' opens the GameStarterScreen."""
        from htop_tycoon.ui.screens.game_starter import GameStarterScreen
        self.push_screen(GameStarterScreen())

    def action_save(self) -> None:
        """Spec §4.1: 'F2' / 'S' saves current state via persistence layer."""
        from pathlib import Path

        from htop_tycoon.persistence import save_state
        target = Path.home() / ".htop_tycoon_save.json"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            save_state(target, self._state)
            self.query_one("#content", Static).update(
                f"[green]저장 완료 (saved to {target})[/]"
            )
        except Exception as exc:  # noqa: BLE001
            self.query_one("#content", Static).update(
                f"[red]저장 실패 (save failed): {exc}[/]"
            )

    def action_toggle_auto(self) -> None:
        """Spec §3.3: 'd' toggles auto mode on/off."""
        self.auto_mode = not self.auto_mode
        status = "ON" if self.auto_mode else "OFF"
        self.query_one("#content", Static).update(
            f"[#39ff14]Auto 모드: {status}[/]"
        )

    def action_toggle_pause(self) -> None:
        """Spec §4.1: 'p' toggles pause (speed = 0 ↔ previous speed)."""
        if self.speed == 0:
            self.speed = 1  # resume at default 1x
        else:
            self.speed = 0
        # Recompute tick interval based on new speed
        if self.speed > 0:
            self.set_interval(1.0 / self.speed, self._tick_one_day)
        status = "재개 (resumed)" if self.speed > 0 else "일시정지 (paused)"
        self.query_one("#content", Static).update(f"[#39ff14]{status}[/]")

    def action_speed_0(self) -> None:
        self.speed = 0
        self.query_one("#content", Static).update("[#39ff14]속도: 정지 (0)[/]")

    def action_speed_1(self) -> None:
        self.speed = 1
        self.query_one("#content", Static).update("[#39ff14]속도: 1x[/]")

    def action_speed_2(self) -> None:
        self.speed = 2
        self.query_one("#content", Static).update("[#39ff14]속도: 2x[/]")

    def action_speed_3(self) -> None:
        self.speed = 3
        self.query_one("#content", Static).update("[#39ff14]속도: 3x[/]")

    def action_speed_4(self) -> None:
        self.speed = 4
        self.query_one("#content", Static).update("[#39ff14]속도: 4x (QA)[/]")

    def action_quit_or_sell(self) -> None:
        """Spec §4.1: F10/q opens the quit/sell dialog (Wave 6+ follow-up)."""
        from pathlib import Path

        from htop_tycoon.persistence import save_state
        target = Path.home() / ".htop_tycoon_save.json"
        try:
            save_state(target, self._state)
        except Exception:  # noqa: BLE001
            pass
        self.exit()

    def action_cursor_up(self) -> None:
        self.query_one("#content", Static).update("[dim]↑ (Wave 6+: table navigation)[/]")

    def action_cursor_down(self) -> None:
        self.query_one("#content", Static).update("[dim]↓ (Wave 6+: table navigation)[/]")

    def action_select(self) -> None:
        self.query_one("#content", Static).update("[dim]Enter (Wave 6+: select row)[/]")

    def action_close_modal(self) -> None:
        # Spec §4.1: Escape closes any open modal.
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_awards(self) -> None:
        self.query_one("#content", Static).update("[dim]a — 시상식 (Wave 6+: modal)[/]")

    def action_console_mgmt(self) -> None:
        self.query_one("#content", Static).update("[dim]c — 콘솔 관리 (Wave 6+: modal)[/]")

    def action_view_project(self) -> None:
        self.query_one("#content", Static).update(
            "[dim]g — 프로젝트 진행 보기 (Wave 6+: screen)[/]"
        )

    def action_search_employee(self) -> None:
        self.query_one("#content", Static).update("[dim]/ — 직원 검색 (Wave 6+: input)[/]")

    def action_filter(self) -> None:
        self.query_one("#content", Static).update("[dim]\\\\ — 필터 (Wave 6+: input)[/]")

    def action_sort_cycle(self) -> None:
        self.query_one("#content", Static).update("[dim]/ — 정렬 사이클 (Wave 6+)[/]")

    def action_promote(self) -> None:
        self.query_one("#content", Static).update("[dim]] — 승진 (Wave 6+: input)[/]")

    def action_demote(self) -> None:
        self.query_one("#content", Static).update("[dim][ — 감봉 (Wave 6+: input)[/]")

    def action_fire(self) -> None:
        self.query_one("#content", Static).update("[dim]k — 해고 (Wave 6+: input)[/]")

    def action_toggle_dept_tree(self) -> None:
        self.query_one("#content", Static).update("[dim]t — 부서 트리 토글 (Wave 6+)[/]")


__all__ = ["HtopTycoonApp"]
