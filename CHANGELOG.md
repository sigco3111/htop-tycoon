# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-25

### Added
- htop 경영 시뮬레이터 Deep scope initial release: htop-styled TUI business simulator (CPU = 매출, 메모리 = 재고, 스왑 = 부채, 좀비 = 퇴사 위기 직원).
- 5 endings (BANKRUPTCY, GOLDEN_PARACHUTE, EMPIRE, SECRET, MONOPOLY) reachable with crafted seeds.
- 5 departments: 경영지원, 마케팅, 개발, 영업, 물류.
- 3 products and 3 competitors in deterministic market simulation.
- Korean UI by default (F1 도움말, F2~F10 bindings + single-key bindings mirror htop).
- Seedable deterministic simulation via `GameRNG(seed)`: same seed produces identical state hash.
- JSON save/load with atomic write + backup, safe corruption recovery (`CORRUPTION_RECOVERY_SEED = 0`).
- CLI entry point: `python -m htop_tycoon` with flags `--seed`, `--tick-rate`, `--load`, `--no-autosave`, `--dev`, `--ending`, `--ticks`.
- Autosave support in headless mode.
- Determinism regression guard (T2): frozen state hash at tick 1000 for seed=42.
- Pilot integration tests (startup, F-keys, save/load).
- Console script `htop-tycoon` for `pip install` / `uv tool install` users.
- Distribution artifacts: wheel + sdist built via `uv build` and uploaded to GitHub Release `v0.1.0`.

### Changed
- N/A (initial release).

### Fixed
- N/A (initial release).

### Known Limitations
- PyPI publishing is a manual step for v0.1.0; the release workflow builds and attaches artifacts to the GitHub Release but does not push to PyPI. Use `twine upload dist/*` after the release artifacts are published.
- Linux and macOS are the primary supported platforms with full CJK rendering audit. Windows console support is best-effort: CJK width behavior may differ on Windows Terminal legacy mode; CI matrix runs pytest only on Windows (no Pilot snapshot tests).
- Single-player only. No multiplayer, online, or networked play. No psutil, SQLite, sound, mobile builds, web GUI, achievements, tutorial branches, difficulty modifiers, modding, or replay framework.
- Time scale is fixed at 1 real-second = 1 game-week. Balance tuning must be done via `src/htop_tycoon/data/balance.yaml` and `seeds.yaml`; changing the time scale in code is forbidden.
- All numeric game constants live in `balance.yaml` (no magic numbers like -500 or +300 in source or data). Do not introduce hardcoded numeric constants outside YAML.
- Determinism invariant: all RNG flows must go through `GameRNG(seed)`. `import random` outside `src/htop_tycoon/rng.py` is rejected by the test suite.
- Scope ceiling: maximum 5 endings, 5 departments, 3 products, 3 competitors. Any expansion requires a plan revision and a new wave note.

## [0.2.0] - 2026-06-30

### Added (Wave 7: Market Regimes)
- Macro regime cycle: BOOM / NORMAL / RECESSION / CRISIS. Each cycle has min/max weeks + weighted transitions + per-regime modifiers (revenue_multiplier, salary_growth_multiplier, competitor_aggression_baseline, event_probability_scale, cash_shock_probability).
- regime_step() pure-function engine: increments weeks, samples next regime at boundary, rolls per-tick CRISIS cash shock (deterministic via GameRNG).
- Engine integration: `engine/metrics.py` revenue flow × regime.revenue_multiplier; `engine/competitor_ai.py` aggression baseline + comp.aggression; `engine/event_chain.py` probability × regime.scale. **NORMAL regime = identity** (multiplier 1.0).
- UI: GameHeader now shows `경기:<label><trend>` with regime-specific CSS class (BOOM green / CRISIS red+bold).

### Added (Wave 8: Department Focus)
- 14 FocusType members: BALANCED universal + 3 per dept (Engineering: QUALITY/SPEED/COST; Sales: AGGRESSIVE/CONSERVATIVE/RELATIONSHIP; Operations: EFFICIENCY/SAFETY/SCALE; Marketing: BRAND/PERFORMANCE/VIRAL; Finance: CONSERVATIVE_FIN/GROWTH/HEDGE).
- FocusChoice(dept_id, focus, set_tick): per-department strategic posture; new GameState.dept_focus field.
- apply_focus_modifier(): combines raw focus × regime metric multiplier, clamps to [0.5, 2.0].
- FocusPickerScreen modal: 5 dept rows with current focus; cooldown guard (set_tick==0 free first change, then `set_tick + cooldown_weeks=16` boundary).
- engine/actions.py::hire(): bias starting_skill upper bound when dept focus is COST/HEDGE/CONSERVATIVE_FIN.
- engine/ai_focus_policy.py: regime-aware focus heuristic applied under Auto-Manager delegation (CRISIS+low-cash → cost-like focus; BOOM+high-cash → growth-like focus; respects T43 cooldown).

### Schema (T45)
- SCHEMA_VERSION bumped 1 → 2. v1 saves auto-migrate on load via persistence.migration.upgrade_v1_to_v2 (adds regime + dept_focus defaults; bumps version).
- Unknown future versions fall through to corruption recovery (`CORRUPTION_RECOVERY_SEED = 0`).

### Frozen hash (T46)
- test_playthrough.py EXPECTED_END_TICK 13 → 54 and EXPECTED_BANKRUPTCY_HASH → 0abd86f0c96f085066709e50422fd5b28cbc8408ffcbe1a870254e5d4313d379 (regime + dept_focus mechanics extend the path to bankruptcy but determinism holds).
- tests/test_no_regression.py pins state_hash(new_game(seed=42)) = 775a57d7014ea7c7798b95715c355630a8bd868939f052c1b855fd380fac88c5 as the v2 default-state source of truth.

### Known issues (deferred — T46 follow-up)
- ~63 v0.1.0 frozen-hash tests in test_endings_reachable.py, test_deserialize.py, test_load.py, test_pilot_integration.py, test_cli.py, test_tick_determinism.py, test_single_key_bindings_pilot.py, test_product.py, test_product_market.py, test_save_load_pilot.py, test_serialize.py still pin v0.1.0 baselines. These will be re-tuned in a follow-up wave before the v0.2.0 GitHub Release. The CORE playthrough (T32) and v2 default (test_no_regression) lock-ins are correct.
