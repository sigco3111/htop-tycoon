# Changelog

All notable changes to htop-tycoon are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [3.1] - 2026-07-03 — Watcher Mode

**핵심 컨셉**: 게임 시작 시 모든 결정이 AI에게 자동 위임됨. 사용자는 **순수 옵저버**(observer)가 되어 화면을 보면서 메트릭을 감상.

### Added
- **메타 전략 선택기** (`src/htop_tycoon/engine/strategy/meta_strategy.py`): 매 tick마다 게임 상태(현금/직원수/프로젝트/좀비)를 보고 최적의 전략 자동 선택. 우선순위 캐스케이드:
  1. cash < 0 OR (cash < $20k AND 좀비 존재) → **CONSERVATIVE**
  2. cash ≥ $100k AND 직원 < 5 → **AGGRESSIVE**
  3. focus_genre 설정 + 진행 중 focus 프로젝트 없음 → **GENRE_FOCUS**
  4. cash ≥ $100k AND 직원 ≥ 7 → **GENRE_FOCUS**
  5. 그 외 → **BALANCED**
- **자동 실행 엔진** (`src/htop_tycoon/engine/auto.py`): 한 tick 안에서 모든 AI 결정을 자동 실행:
  - 전략 자동 변경
  - 자동 채용 (strategy가 hire 결정 시 가장 강한 후보)
  - 자동 해고 (cash < $20k + 좀비 우선)
  - 자동 출시 (출시 가능 프로젝트 → 가장 저렴한 콘솔)
  - 자동 콘솔 구매 (cash ≥ $80k + 미보유)
  - 자동 자발적 매각 (mega_hit ≥ 1 + cash ≥ $200k)
- **CLI 기본값**: `__main__.py`에서 `state.auto_on=True`로 시작 (v3.0.1에서는 `False`였음).

### Changed
- `engine/tick.py`: `state.auto_on`이 `True`이면 `_apply_strategy_decisions` 대신 `auto_execute` 호출.
- `ui/app.py`: 모든 `action_open_*` 메서드(전략/고용/해고/출시/콘솔/매각/새프로젝트)가 `auto_on=True`일 때 모달을 열지 않고 "자동 모드 — AI가 ...을 처리합니다" notify만 표시.

### 동작 방식
- 시작 시 자동으로 AI가 메타 전략을 선택하고, 직원 채용, 콘솔 구매 등을 알아서 진행.
- `d` 키로 수동 모드 토글 가능 (`auto_on=False`로 전환).
- 수동 모드에서는 기존과 같이 모달이 뜨고 사람이 직접 결정.
- 다시 `d` 누르면 자동 모드로 복귀.

### Tests
- 신규: `tests/test_meta_strategy.py` (7개), `tests/test_auto_execute.py` (10개), `tests/test_auto_tick_dispatch.py` (3개), `tests/pilot/test_auto_mode.py` (7개), `tests/test_main_auto_default.py` (4개) — 총 +31개.
- **468 tests pass** (437 + 31).

## [3.0.1] - 2026-07-02

### Fixed
- **BINDINGS 키 충돌**: 동일 키(`1`/`2`/`3`/`4`/`0`)가 4-5개 액션에 중복 바인딩되어 마지막 것만 동작하던 문제 해결. `action_route_digit` 단일 라우터 도입으로 모달 컨텍스트 자동 분기.
- **F9 키 매핑 수정**: `F9=Load` → `F9=해고`로 사용자 의도대로 변경. `F8=Load`로 이동.
- **"s 전략" → 밸런스만 선택됨** 문제: `1`/`2`/`4` 키 충돌로 동작 안 하던 것 수정. 모달 컨텍스트 라우터로 4종 전략 모두 정상 선택.
- **Speed 단축키**: `1`/`2`/`3`/`4` 키가 다른 액션에 가로채이던 문제 해결. 모달 없을 때 속도 변경, 모달 있을 때 모달 선택.
- **Auto 모드 단축키**: `d` 키로 Auto ON/OFF 토글.
- **n 새 게임 프로젝트 단축키**: `n` 키로 새 프로젝트 시작 (장르 모달).
- **Space 직원 태그**: placeholder notify.

### Added
- `F1` 도움말 화면 (HelpScreen): 모든 키바인딩 + 전략 + 엔딩을 한 화면에 표시.
- `F3` 검색 화면 (SearchScreen): 직원 이름으로 부분 매칭 검색.
- `F5` 트리 토글: OrgTree 펼침/접기 상태 표시.
- `F7` 승진 화면 (PromoteScreen): LEAD 직원 만족도 순으로 승진 가능 여부 표시.
- `i18n` 모듈: `ko_label`, `ko_money`, `BINDINGS_KO`, `JOB_KO`, `DEPT_KO`, `GENRE_KO`, `STRATEGY_KO`, `ENDING_KO`, `METRIC_KO`, `EVENT_KIND_KO`, `NOTIFY_KO` 등 통합 한글 사전.

### Changed
- **전체 UI 한글화**: Header / Footer / OrgTree / MetricBar / EventLog / 모든 모달 화면이 한글로 표시.
- **Footer 동적 속도 표시**: `MOCK_SPEED_LABEL`/`MOCK_AUTO_LABEL` 제거.
- **Engine 한영 공존**: `ENDING_LABELS`/`ENDING_DESCRIPTIONS` (영문) + `ENDING_KO`/`ENDING_DESCRIPTIONS_KO` (한글) 모두 보존. Strategy 클래스에 `name_ko`/`description_ko` 추가.
- **모든 notify 메시지 한글화**: "Saved:" → "저장됨:", "Hired:" → "고용됨:", "Fired:" → "해고:" 등.
- **버전 3.0.0 → 3.0.1**: 버그 수정 + 한글화. 테스트 327개 → 437개.

### Tests
- 신규 4개 테스트 파일: `tests/ui/test_i18n.py` (49 tests), `tests/pilot/test_bindings_router.py` (21 tests), `tests/pilot/test_new_actions.py` (7 tests), `tests/pilot/test_new_screens.py` (14 tests).
- 기존 테스트 업데이트: 한글 표시에 맞게 assertions 수정 (`Year 1` → `1년차`, `LEAD` → `리드`, `ZOMBIE` → `좀비` 등).

## [3.0.0] - 2026-07-02

### Added (v3.0 from scratch)

Phase 1부터 Phase 2L까지 13개 phase를 거쳐 완전 재작성. 이전 v0.2.0 구현은 의도적으로 폐기 (사용자 요청: "이전 작업은 너무 엉망이였어. 참고 하지말고 처음부터 시작해").

#### Phase 1: htop chrome (TUI foundation)
- Terminal-green htop-style TUI: Header (Year/Cash/Fans/Strategy) + Footer (F-key hints + Speed/Auto)
- Textual-based, runs at 120x40 default
- Phosphor-green theme (`#39ff14`) on near-black (`#0a0a0a`)

#### Phase 2A: Domain core (23 types)
- `Money(cents)` frozen + arithmetic + display (`$1,000`, thousands separator)
- `QualityAxes(fun, graphics, sound, originality)` clamped 0..100
- `Progress(value)` clamped 0..100, `is_complete`
- `EmployeeId`/`ProjectId`/`CompanyId` branded `int` subclasses
- `GameTitle` validated `str` (rejects empty/whitespace)
- `Job`/`Genre`/`Platform`/`Console`/`Department`/`SatisfactionTier`/`StrategyKind` StrEnums
- `Employee` (frozen, `promote()`, `is_zombie`, `compute_salary`)
- `GameProject` (frozen, `is_shipped`, `team_ids` tuple)
- `CompanyState` aggregate (non-frozen, mutable employees/projects dicts)
- `GameRng(seed)` deterministic RNG with `int_range`, `choice`, `weighted_choice`, `shuffle`, `sample`

#### Phase 2B: Engine — tick + sales
- `compute_employee_productivity(emp, rng)` formula
- `compute_daily_progress(project, state, rng)` and `advance_projects(state, rng)`
- `compute_sales_revenue(project, market, rng)` with platform/console/genre/quality multipliers
- `tick(state, rng, market)` orchestrates: salaries → satisfaction drift → advance → ship → day

#### Phase 2C: OrgTree widget
- Textual `Tree[str]` grouped by `Department`
- `nice_value(job, level)` → `"LEAD 5"` format
- Zombie marker `[Z]` for `satisfaction < 20`
- 6 employees + 4 depts (mock_state) with real salaries

#### Phase 2D: MetricBar widget
- 4-axis quality bars: FUN, GRAPHICS, SOUND, ORIGINAL
- ASCII bar chars: `█` (filled) + `░` (empty)
- 10-char width, `pick_active_project(state)` selects lowest-progress

#### Phase 2E: Timer + speed control
- Textual `set_interval` integration
- Speed 0-4: 0=paused, 1-3=user speeds, 4=headless QA
- `MIN_SPEED = 0` (was 1) so 0 means paused per README
- BINDINGS: 0/1/2/3/4/p

#### Phase 2F: Save/Load YAML v2
- `pyyaml>=6.0.1` + `types-PyYAML`
- `atomic_write(path, content)` via tmp + `os.replace`
- `rotate_backups(directory, name, keep=3)` (.1.yaml, .2.yaml, ...)
- `save_state(state, path)` + `load_state(path)`
- `to_yaml` / `from_yaml` with `PersistenceVersionError`
- `SAVE_PATH` resolver with `HTOP_TYCOON_SAVE_DIR` env override
- BINDINGS: F2/F9

#### Phase 2G: Ending system
- 5 ending kinds: BANKRUPTCY, VOLUNTARY_SALE, MEGA_HIT, HALL_OF_FAME, SECRET
- `detect_ending(state)` priority cascade (hard > soft)
- `record_ending(state, ending)` idempotent per kind
- `LegacyScore` snapshot, `CompanyState.legacy_scores` field
- `EndingScreen` modal, `LegacyPanel` body widget
- BINDINGS: F10 (voluntary sale)
- Schema bump: v1 → v2 (backward compat for old saves via `.get(key, default)`)

#### Phase 2H: StrategyPicker + 4 strategies
- `Strategy` ABC with `decide(state, rng) → list[StrategyDecision]`
- `StrategyDecision` frozen dataclass (action, target, magnitude, reason)
- 4 strategies: Aggressive, Conservative, Balanced, GenreFocus
- `STRATEGY_REGISTRY` dispatch + `current_strategy(state)`
- `StrategyPicker` modal with `→ Balanced ←` arrow markers
- BINDINGS: S + 1-4

#### Phase 2I: Hire/Fire employee management
- `engine/hr.py`: `HireCandidate`, `hire_employee`, `fire_employee`, `generate_candidates`
- 30-name candidate pool + auto EmployeeId
- `HireScreen` / `FireScreen` modals (Fire sorts by satisfaction asc, [ZOMBIE] markers)
- BINDINGS: H/X + 5-8/9

#### Phase 2J: Releases + ConsoleMarket
- `engine/console_market.py`: `CONSOLE_PRICES` (PC free, $40k-$150k), `purchase_console`
- `engine/release.py`: `release_project(state, pid, target_console, market, rng)`
- `ReleaseScreen` / `ConsoleMarketScreen` modals
- BINDINGS: R/C

#### Phase 2K: Strategy auto-apply
- `engine/event_log.py`: `Event` (frozen) + `EventKind` (StrEnum)
- `CompanyState.event_log` field
- `_apply_strategy_decisions(state, rng)` in `tick()`:
  - All decisions recorded in event_log
  - `fire zombie` auto-applied (Conservative)
  - `hire` auto-applied via `generate_candidates` (Aggressive/Balanced)
  - `start_project` / `save_cash` / `boost_funding` log only

#### Phase 2L: EventLogPanel (strategy decision feed)
- `ui/widgets/event_log.py`: `EventLogPanel(state)` body widget
- Renders last 5 events from `state.event_log` with kind + day_index + description
- Pure renderer (no state mutation, no side effects)
- Mounted in `App.compose()` between `MetricBar` and `LegacyPanel`
- `_refresh_widgets()` re-mounts EventLogPanel + LegacyPanel on every tick
- Format: `Y{year}D{day} {kind:<18} {description}`
- Empty state: "Event Log (no events yet — wait for strategy to fire)"

### Changed

- `CompanyState.speed` default 1 → 0 (paused; speed=0 must be valid)
- Domain widening with backward-compatible defaults across all 13 phases

### Tests

- **334 total tests** across 92 source files
- 90%+ coverage maintained (currently 90%)
- All Phase 1-2L pilot SVGs regenerated and captured in `docs/screenshots/`

### Known Limitations / Future Work

- Promote/Demote (F7/F8) — domain method `Employee.promote()` exists but no UI binding
- Awards screen (A) — no implementation yet
- Console hardware lifecycle (used vs new) not tracked separately
- Strategy decisions like `start_project` need user input (genre/team) so only logged

## [0.2.0] - 2026-06 (legacy)

Pre-v3.0 implementation. v0.2.0 → Wave 6 UI was deleted at start of v3.0 (per user direction "이전 작업은 너무 엉망이였어. 참고 하지말고 처음부터 시작해").

[3.0.0]: https://github.com/sigco3111/htop-tycoon/compare/main...v3.0
