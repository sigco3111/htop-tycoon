"""HtopTycoonApp — root Textual application.

Phase 2G: engine tick + speed control + save/load + ending detection.
Key bindings 0/1/2/3/4 set speed, p toggles pause, q quits,
f2 saves, f9 loads, F10 requests voluntary sale. State is injected
(defaults to mock_state); rng defaults to seeded GameRng.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.domain import CompanyState
from htop_tycoon.domain.enums import Console, StrategyKind
from htop_tycoon.domain.rng import GameRng
from htop_tycoon.engine import (
    DEFAULT_MARKET,
    HARD_ENDINGS,
    MarketState,
    construct_legacy_score,
    detect_ending,
    fire_employee,
    generate_candidates,
    hire_employee,
    purchase_console,
    record_ending,
    release_project,
    tick,
)
from htop_tycoon.persistence import SAVE_PATH, load_state, save_state
from htop_tycoon.ui.i18n import bind_en_ko
from htop_tycoon.ui.mock_state import mock_state
from htop_tycoon.ui.screens.console import ConsoleMarketScreen
from htop_tycoon.ui.screens.ending import EndingScreen, LegacyPanel
from htop_tycoon.ui.screens.fire import FireScreen
from htop_tycoon.ui.screens.help import HelpScreen
from htop_tycoon.ui.screens.hire import HireScreen
from htop_tycoon.ui.screens.new_project import NewProjectScreen
from htop_tycoon.ui.screens.promote import PromoteScreen
from htop_tycoon.ui.screens.release import ReleaseScreen
from htop_tycoon.ui.screens.search import SearchScreen
from htop_tycoon.ui.screens.strategy_picker import StrategyPicker
from htop_tycoon.ui.theme import HtopTycoonTheme
from htop_tycoon.ui.widgets.event_log import EventLogPanel
from htop_tycoon.ui.widgets.footer import Footer as HtopFooter
from htop_tycoon.ui.widgets.header import Header as HtopHeader
from htop_tycoon.ui.widgets.metric_bar import MetricBar
from htop_tycoon.ui.widgets.org_tree import OrgTree

if TYPE_CHECKING:
    from textual.timer import Timer as Interval  # alias for readability


class HtopTycoonApp(App[int]):
    """Root app for the htop-tycoon v3.0 TUI.

    Phase 2G surfaces:
    - Terminal-green theme registered + selected.
    - Header / OrgTree / MetricBar / LegacyPanel / Footer mounted, driven by state.
    - Timer advances state by one day per interval (speed-dependent).
    - BINDINGS for speed (0/1/2/3/4), pause toggle (p), save (f2),
      load (f9), sell (F10), quit (q).
    - Hard ending detection pauses the timer + pushes EndingScreen modal.
    """

    TITLE: str = "htop-tycoon v3.0"
    SUB_TITLE: str = "Kairosoft Game Dev Story — htop edition"

    BINDINGS = [
        *bind_en_ko("0", "route_digit('0')", "정지", show=True),
        *bind_en_ko("1", "route_digit('1')", "1x", show=True),
        *bind_en_ko("2", "route_digit('2')", "2x", show=True),
        *bind_en_ko("3", "route_digit('3')", "3x", show=True),
        *bind_en_ko("4", "route_digit('4')", "4x", show=True),
        *bind_en_ko("p", "toggle_pause", "일시정지", show=True),
        *bind_en_ko("f1", "show_help", "도움말", show=True),
        *bind_en_ko("f2", "save_game", "저장", show=True),
        *bind_en_ko("f3", "search_employee", "검색", show=True),
        *bind_en_ko("f5", "toggle_tree", "트리", show=True),
        *bind_en_ko("f7", "promote_employee", "승진", show=True),
        *bind_en_ko("f8", "load_game", "로드", show=True),
        *bind_en_ko("f9", "open_fire_screen", "해고", show=True),
        *bind_en_ko("f10", "request_sell", "매각", show=True),
        *bind_en_ko("s", "open_strategy_picker", "전략", show=True),
        *bind_en_ko("h", "open_hire_screen", "고용", show=True),
        *bind_en_ko("x", "open_fire_screen", "해고", show=True),
        *bind_en_ko("c", "open_console_market", "콘솔", show=True),
        *bind_en_ko("n", "new_project", "새게임", show=True),
        *bind_en_ko("d", "toggle_auto", "자동", show=True),
        *bind_en_ko("space", "tag_employee", "태그", show=True),
        *bind_en_ko("q", "quit", "종료", show=True),
    ]

    def __init__(
        self,
        state: CompanyState | None = None,
        rng: GameRng | None = None,
        market: MarketState | None = None,
        save_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.register_theme(HtopTycoonTheme())
        self.theme = HtopTycoonTheme().name
        self._state: CompanyState = state if state is not None else mock_state()
        self._rng: GameRng = rng if rng is not None else GameRng(self._state.rng_seed)
        self._market: MarketState = market if market is not None else DEFAULT_MARKET
        self._save_path: Path = save_path if save_path is not None else SAVE_PATH
        self._tick_interval: Interval | None = None
        self._tick_count: int = 0
        self._pending_ending_screen: EndingScreen | None = None
        self._pending_strategy_picker: StrategyPicker | None = None
        self._pending_hire_screen: HireScreen | None = None
        self._pending_fire_screen: FireScreen | None = None
        self._pending_release_screen: ReleaseScreen | None = None
        self._pending_console_screen: ConsoleMarketScreen | None = None
        self._pending_release_target: Console | None = None
        self._pending_help_screen: HelpScreen | None = None
        self._pending_search_screen: SearchScreen | None = None
        self._pending_promote_screen: PromoteScreen | None = None
        self._pending_new_project_screen: NewProjectScreen | None = None
        self._tree_expanded: bool = True

    def compose(self) -> ComposeResult:
        yield HtopHeader(state=self._state)
        with Vertical(id="body"):
            yield OrgTree(self._state)
            yield MetricBar(self._state)
            yield Static(EventLogPanel(self._state).render())
            yield Static(LegacyPanel(self._state.legacy_scores).render())
        yield HtopFooter(state=self._state)

    def _refresh_header(self) -> None:
        main_screen = self.screen_stack[0]
        old = list(main_screen.query(HtopHeader))
        for h in old:
            h.remove()
        main_screen.mount(HtopHeader(state=self._state), before=0)

    def _refresh_legacy(self) -> None:
        legacy = self.query("Static")[-1]  # last Static in body
        if hasattr(legacy, "update"):
            legacy.update(LegacyPanel(self._state.legacy_scores).render())

    def on_mount(self) -> None:
        self._restart_timer()

    def on_unmount(self) -> None:
        if self._tick_interval is not None:
            self._tick_interval.stop()
            self._tick_interval = None

    def _restart_timer(self) -> None:
        if self._tick_interval is not None:
            self._tick_interval.stop()
            self._tick_interval = None
        if self._state.speed > 0:
            interval_seconds = 1.0 / self._state.speed
            self._tick_interval = self.set_interval(
                interval_seconds,
                self._advance_one_tick,
                name="tick",
            )

    def _advance_one_tick(self) -> None:
        if self._is_modal_open():
            return
        self._state = tick(self._state, self._rng, self._market)
        self._tick_count += 1
        ending = detect_ending(self._state)
        if ending is not None and ending.kind in HARD_ENDINGS:
            self._state = self._state.set_speed(0)
            self._state = record_ending(self._state, ending)
            legacy = construct_legacy_score(self._state, ending)
            modal = EndingScreen(ending, legacy)
            self._open_pending("_pending_ending_screen", modal)
            self._restart_timer()
        self._refresh_header()
        self._refresh_widgets()

    def _refresh_widgets(self) -> None:
        if self._is_modal_open():
            self._refresh_footer()
            return
        try:
            body = self.query_one("#body", Vertical)
        except Exception:
            return
        try:
            orgtree = self.query_one(OrgTree)
            orgtree.update_state(self._state)
            for child in list(body.children):
                if not isinstance(child, OrgTree):
                    child.remove()
            body.mount(MetricBar(self._state))
            body.mount(Static(LegacyPanel(self._state.legacy_scores).render()))
        except Exception:
            body.remove_children()
            body.mount(OrgTree(self._state))
            body.mount(MetricBar(self._state))
            body.mount(Static(LegacyPanel(self._state.legacy_scores).render()))
        self._refresh_footer()

    def _is_modal_open(self) -> bool:
        return any(
            pending is not None
            for pending in (
                self._pending_strategy_picker,
                self._pending_hire_screen,
                self._pending_fire_screen,
                self._pending_release_screen,
                self._pending_console_screen,
                self._pending_promote_screen,
                self._pending_search_screen,
                self._pending_help_screen,
                self._pending_new_project_screen,
                self._pending_ending_screen,
            )
        )

    def _refresh_footer(self) -> None:
        try:
            footer = self.query_one(HtopFooter)
            footer.update_status(self._state)
        except Exception:
            pass

    def action_set_speed(self, speed: int) -> None:
        self._state = self._state.set_speed(speed)
        self._restart_timer()
        self._refresh_footer()

    def _open_pending(self, attr: str, modal: ModalScreen[None]) -> None:
        """Push modal screen onto stack and keep _pending_<x>_screen alias in sync.

        The dismiss callback clears the alias if it's still pointing at this modal.
        """
        setattr(self, attr, modal)

        def _on_dismiss(_result: object = None) -> None:
            if getattr(self, attr, None) is modal:
                setattr(self, attr, None)

        self.push_screen(modal, callback=_on_dismiss)

    def _close_modal(self) -> None:
        """Close the top modal screen and clear its _pending alias.

        Uses App.pop_screen for the standard dismiss lifecycle (cleanup
        callback fires) plus synchronous _pending cleanup so the modal
        disappears from screen_stack immediately and _is_modal_open()
        returns False by the time pilot.pause() resumes.

        Without synchronous cleanup, Textual's dismiss callback is
        scheduled via call_next (asynchronous) and _pending stays set
        after the modal is gone — _is_modal_open() stays True.
        """
        _pending_attrs = (
            "_pending_strategy_picker",
            "_pending_hire_screen",
            "_pending_fire_screen",
            "_pending_release_screen",
            "_pending_console_screen",
            "_pending_promote_screen",
            "_pending_search_screen",
            "_pending_help_screen",
            "_pending_new_project_screen",
            "_pending_ending_screen",
        )
        if len(self.screen_stack) > 1:
            modal = self.screen_stack[-1]
            for attr in _pending_attrs:
                if getattr(self, attr) is modal:
                    setattr(self, attr, None)
            self.pop_screen()
        for attr in _pending_attrs:
            if getattr(self, attr) is not None:
                setattr(self, attr, None)

    def action_digit(self, key: str) -> None:
        """Forward a digit key from a ModalScreen to the router."""
        self.action_route_digit(key)

    def action_close_top_modal(self) -> None:
        """Esc 핸들러 (모든 ModalScreen BINDINGS escape에서 호출).

        동기적으로 screen_stack pop + _pending_* 모두 정리.
        _close_modal()과 동일하지만 action으로 노출하여
        ModalScreen BINDINGS에서 직접 호출 가능.
        """
        self._close_modal()

    def action_toggle_pause(self) -> None:
        new_speed = 0 if self._state.speed > 0 else 1
        self.action_set_speed(new_speed)

    def action_save_game(self) -> None:
        try:
            save_state(self._state, self._save_path)
            self.notify(f"저장됨: {self._save_path}")
        except OSError as exc:
            self.notify(f"저장 실패: {exc}")

    def action_load_game(self) -> None:
        try:
            self._state = load_state(self._save_path)
        except FileNotFoundError:
            self.notify("저장 파일이 없습니다")
            return
        except OSError as exc:
            self.notify(f"로드 실패: {exc}")
            return
        self._refresh_header()
        self._refresh_widgets()
        self.notify("로드됨")

    def action_request_sell(self) -> None:
        if self._state.auto_on:
            self.notify("자동 모드 — AI가 매각을 처리합니다")
            return
        self._state = self._state.set_voluntary_sale_pending(True)
        self.notify("매각 요청 대기열 추가 — 다음 tick에 현금 ≥ $200,000이면 발동")
        self._refresh_widgets()

    def action_open_strategy_picker(self) -> None:
        if self._state.auto_on:
            self.notify("자동 모드 — AI가 전략을 선택합니다")
            return
        modal = StrategyPicker(self._state.strategy)
        self._open_pending("_pending_strategy_picker", modal)
        self.notify(
            f"전략 선택 (현재: {self._state.strategy.value}). 1-4 키로 변경."
        )

    def action_select_strategy(self, kind_str: str) -> None:
        kind = StrategyKind(kind_str)
        self._state = self._state.set_strategy(kind)
        self._pending_strategy_picker = None
        self.notify(f"전략: {kind.value}")
        self._refresh_header()
        self._refresh_widgets()
        self._close_modal()

    def action_open_hire_screen(self) -> None:
        if self._state.auto_on:
            self.notify("자동 모드 — AI가 채용을 처리합니다")
            return
        used = {e.name for e in self._state.employees.values()}
        modal = HireScreen(
            generate_candidates(self._rng, count=5, used_names=used)
        )
        self._open_pending("_pending_hire_screen", modal)
        self.notify(f"고용: 후보 {len(modal.candidates)}명")

    def action_select_candidate(self, idx_str: str) -> None:
        if self._pending_hire_screen is None:
            return
        candidate = self._pending_hire_screen.select(int(idx_str))
        if candidate is None:
            self.notify("잘못된 선택")
            return
        self._state = hire_employee(self._state, candidate)
        self.notify(f"고용됨: {candidate.name} ({candidate.job.value} L{candidate.suggested_level})")
        self._pending_hire_screen = None
        self._refresh_header()
        self._refresh_widgets()
        self._close_modal()

    def action_open_fire_screen(self) -> None:
        if self._state.auto_on:
            self.notify("자동 모드 — AI가 해고를 처리합니다")
            return
        if not self._state.employees:
            self.notify("해고할 직원이 없습니다")
            return
        modal = FireScreen(self._state)
        self._open_pending("_pending_fire_screen", modal)
        self.notify("해고: 직원을 선택하세요 (1-N)")

    def action_select_fire_target(self, idx_str: str) -> None:
        if self._pending_fire_screen is None:
            return
        target_id = self._pending_fire_screen.select(int(idx_str))
        if target_id is None:
            self.notify("잘못된 선택")
            return
        emp_name = self._state.employees[target_id].name
        self._state = fire_employee(self._state, target_id)
        self._pending_fire_screen = None
        self.notify(f"해고: {emp_name}")
        self._refresh_header()
        self._refresh_widgets()
        self._close_modal()

    def action_open_release_screen(self) -> None:
        if self._state.auto_on:
            self.notify("자동 모드 — AI가 출시를 처리합니다")
            return
        modal = ReleaseScreen(self._state)
        if not modal.projects:
            self.notify("출시 가능한 프로젝트가 없습니다")
            return
        self._open_pending("_pending_release_screen", modal)

    def action_select_release_target(self, idx_str: str) -> None:
        if self._pending_release_screen is None:
            return
        project_id = self._pending_release_screen.select(int(idx_str))
        if project_id is None:
            self.notify("잘못된 선택")
            return
        from htop_tycoon.engine.console_market import available_consoles

        target = next(
            (c for c in available_consoles() if c != self._state.own_console),
            None,
        )
        if target is None:
            self.notify("출시 가능한 콘솔이 없습니다")
            return
        try:
            self._state = release_project(
                self._state, project_id, target, self._market, self._rng
            )
            self.notify(f"출시 완료: {target.value}")
        except ValueError as exc:
            self.notify(f"출시 실패: {exc}")
            return
        self._pending_release_screen = None
        self._refresh_header()
        self._refresh_widgets()
        self._close_modal()

    def action_open_console_market(self) -> None:
        if self._state.auto_on:
            self.notify("자동 모드 — AI가 콘솔 구매를 처리합니다")
            return
        modal = ConsoleMarketScreen(self._state)
        self._open_pending("_pending_console_screen", modal)

    def action_buy_console(self, idx_str: str) -> None:
        if self._pending_console_screen is None:
            return
        console = self._pending_console_screen.select(int(idx_str))
        if console is None:
            self.notify("잘못된 선택")
            return
        try:
            self._state = purchase_console(self._state, console)
            self.notify(f"구매 완료: {console.value}")
        except ValueError as exc:
            self.notify(f"구매 실패: {exc}")
            return
        self._pending_console_screen = None
        self._refresh_header()
        self._refresh_widgets()
        self._close_modal()

    def action_select_promote_target(self, idx_str: str) -> None:
        if self._pending_promote_screen is None:
            return
        target_id = self._pending_promote_screen.select(int(idx_str))
        if target_id is None:
            self.notify("잘못된 선택")
            return
        emp = self._state.employees.get(target_id)
        if emp is None:
            self.notify("직원을 찾을 수 없습니다")
            self._pending_promote_screen = None
            self._close_modal()
            return
        from htop_tycoon.ui.screens.promote import PromoteScreen
        if (
            emp.job.value != "LEAD"
            or emp.satisfaction < PromoteScreen.PROMOTION_SAT_THRESHOLD
            or emp.level >= PromoteScreen.MAX_LEVEL
        ):
            self.notify(f"{emp.name}은 승진할 수 없습니다")
            self._pending_promote_screen = None
            self._close_modal()
            return
        new_emp = emp.promote()
        new_employees = dict(self._state.employees)
        new_employees[target_id] = new_emp
        import dataclasses
        self._state = dataclasses.replace(self._state, employees=new_employees)
        self.notify(f"승진: {emp.name} L{emp.level} → L{new_emp.level}")
        self._pending_promote_screen = None
        self._refresh_header()
        self._refresh_widgets()
        self._close_modal()

    def action_route_digit(self, key: str) -> None:
        if self._pending_strategy_picker is not None:
            mapping = {
                "1": "AGGRESSIVE",
                "2": "CONSERVATIVE",
                "3": "BALANCED",
                "4": "GENRE_FOCUS",
            }
            if key in mapping:
                self.action_select_strategy(mapping[key])
            return
        if self._pending_hire_screen is not None:
            self.action_select_candidate(key)
            return
        if self._pending_fire_screen is not None:
            self.action_select_fire_target(key)
            return
        if self._pending_release_screen is not None:
            self.action_select_release_target(key)
            return
        if self._pending_console_screen is not None:
            self.action_buy_console(key)
            return
        if self._pending_promote_screen is not None:
            self.action_select_promote_target(key)
            return
        if key in {"1", "2", "3", "4"}:
            self.action_set_speed(int(key))
        elif key == "0":
            self.action_set_speed(0)

    def action_show_help(self) -> None:
        modal = HelpScreen()
        self._open_pending("_pending_help_screen", modal)
        self.notify("도움말 — Esc로 닫기")

    def action_search_employee(self, query: str = "") -> None:
        if query:
            matches = [
                e.name for e in self._state.employees.values()
                if query.lower() in e.name.lower()
            ]
            if not matches:
                self.notify("검색 결과 없음")
                return
            modal = SearchScreen(query=query, candidates=matches)
            self._open_pending("_pending_search_screen", modal)
            self.notify(f"검색 결과: {', '.join(matches)}")
            return
        names = sorted(e.name for e in self._state.employees.values())
        if not names:
            self.notify("직원이 없습니다")
            return
        modal = SearchScreen(query="", candidates=names)
        self._open_pending("_pending_search_screen", modal)

    def action_toggle_tree(self) -> None:
        self._tree_expanded = not self._tree_expanded
        try:
            orgtree = self.query_one(OrgTree)
            if self._tree_expanded:
                orgtree.root.expand()
            else:
                orgtree.root.collapse()
        except Exception:
            pass
        self.notify(f"트리: {'펼침' if self._tree_expanded else '접기'}")

    def action_promote_employee(self) -> None:
        modal = PromoteScreen(self._state)
        self._open_pending("_pending_promote_screen", modal)
        self.notify("승진 대상 선택 (LEAD, 만족도 70%+ 만 가능)")

    def action_new_project(self) -> None:
        if self._state.auto_on:
            self.notify("자동 모드 — AI가 새 프로젝트를 처리합니다")
            return
        from htop_tycoon.domain import (
            GameProject,
            GameTitle,
            Platform,
            Progress,
            ProjectId,
            QualityAxes,
        )
        from htop_tycoon.domain.enums import Genre
        self._pending_new_project_screen = NewProjectScreen()
        if self._state.projects:
            self.notify("이미 진행 중인 프로젝트가 있습니다")
            return
        lead = next(
            (e for e in self._state.employees.values() if e.job.value == "LEAD"),
            None,
        )
        if lead is None:
            self.notify("리드 직원이 없어 프로젝트를 시작할 수 없습니다")
            return
        next_id = max((int(p) for p in self._state.projects.keys()), default=0) + 1
        new_proj = GameProject(
            id=ProjectId(next_id),
            title=GameTitle("New Game"),
            genre=Genre.RPG,
            platform=Platform.PC,
            console=None,
            progress=Progress(0),
            quality=QualityAxes(50, 50, 50, 50),
            days_in_dev=0,
            lead_id=lead.id,
            team_ids=(lead.id,),
        )
        self._state = self._state.add_project(new_proj)
        modal = NewProjectScreen()
        self._open_pending("_pending_new_project_screen", modal)
        self.notify("새 프로젝트 시작: New Game")
        self._refresh_widgets()

    def action_toggle_auto(self) -> None:
        self._state = self._state.toggle_auto()
        self.notify(f"자동: {'ON' if self._state.auto_on else 'OFF'}")
        self._refresh_footer()

    def action_quit(self) -> None:
        """q 키: 현재 state를 save_path에 저장 후 종료."""
        self._auto_save()
        self.exit()

    def quit(self) -> None:
        """모든 종료 path에서 자동 저장."""
        self._auto_save()
        self._exit = True
        self._close_messages_no_wait()

    def _auto_save(self) -> None:
        try:
            save_state(self._state, self._save_path)
        except OSError as exc:
            self.notify(f"자동 저장 실패: {exc}")
            return
        self.notify(f"자동 저장됨: {self._save_path}")

    def action_tag_employee(self) -> None:
        self.notify("태그 기능 곧 출시")
