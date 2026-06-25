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
