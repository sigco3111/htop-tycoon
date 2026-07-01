# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-07-01

### Changed (BREAKING — full reset)
- **Concept pivot**: from generic business sim to TUI port of Kairosoft's Game Dev Story
- **Time scale**: 1 real-sec = 1 game-day (was: 1 real-sec = 1 game-week)
- **5 departments**: 경영/기획/개발/아트/사운드
- **6 base jobs + 1 prestige**: Producer / Game Designer / Programmer / Graphic Artist / Sound Creator / Hacker / HW Engineer (post-Secret)
- **4 quality axes**: 재미/그래픽/사운드/독창성
- **Strategy Manager delegation**: 4 AI strategies (Aggressive / Conservative / Balanced / Genre-Focus)
- **5 endings**: Bankruptcy (forced), Voluntary Sale (forced), Mega Hit (soft), Hall of Fame (soft), Secret (soft)
- **Speed control**: keys 0/1/2/3/4 (0=pause, 1=1x default, 4=headless QA)

### Added
- Korean UI default, English README
- Deterministic seeded simulation via GameRNG(seed)
- JSON save/load with atomic write + backup + corruption recovery
- 3 frozen state hashes at seed=42 day 100/1000/3650
- 5 Pilot UI scenarios
- 7 release gates
- Legacy Score panel with 7 achievements

### Removed
- Market regimes system (BOOM/CRISIS)
- Department focus system (14 focus types)
- v0.2.0 hotfixes (OrgTree dict-shape, persistence reconstruct)

## [0.2.0] - 2026-06-30 (no release tag — branch only)
## [0.1.0] - 2026-06-25 (release tag v0.1.0 only — historical reference)