# Changelog

All notable changes to htop-tycoon are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [3.0.0] - 2026-07-02

### Added (v3.0 from scratch)

Phase 1부터 Phase 2K까지 12개 phase를 거쳐 완전 재작성. 이전 v0.2.0 구현은 의도적으로 폐기 (사용자 요청: "이전 작업은 너무 엉망이였어. 참고 하지말고 처음부터 시작해").

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

### Changed

- `CompanyState.speed` default 1 → 0 (paused; speed=0 must be valid)
- Domain widening with backward-compatible defaults across all 12 phases

### Tests

- 327 total tests across 90 source files
- 90%+ coverage maintained
- All Phase 1+2 pilot SVGs regenerated and captured in `docs/screenshots/`

### Known Limitations / Future Work

- Promote/Demote (F7/F8) — domain method `Employee.promote()` exists but no UI binding
- Awards screen (A) — no implementation yet
- Console hardware lifecycle (used vs new) not tracked separately
- Strategy decisions like `start_project` need user input (genre/team) so only logged

## [0.2.0] - 2026-06 (legacy)

Pre-v3.0 implementation. v0.2.0 → Wave 6 UI was deleted at start of v3.0 (per user direction "이전 작업은 너무 엉망이였어. 참고 하지말고 처음부터 시작해").

[3.0.0]: https://github.com/sigco3111/htop-tycoon/compare/main...v3.0
