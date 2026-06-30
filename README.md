# htop-tycoon — htop 경영 시뮬레이터 / htop-styled TUI Business Simulator

> **Looks like server monitoring at a glance. Actually a deep business simulator.**
> CPU = revenue, memory = inventory, swap = debt, zombie = employees at quitting risk.

*(Korean: 화면 캡처 한 장만 봐도 서버 모니터링 같지만, 사실 회사 경영 게임.
CPU는 매출, 메모리는 재고, 좀비 프로세스는 퇴사 위기 직원.)*

![CI](https://img.shields.io/github/actions/workflow/status/sigco3111/htop-tycoon/ci.yml?style=for-the-badge&label=CI)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue?style=for-the-badge)
![License](https://img.shields.io/github/license/sigco3111/htop-tycoon?style=for-the-badge)
![Version](https://img.shields.io/badge/version-0.1.0-green?style=for-the-badge)

A terminal business simulator that disguises itself as `htop`. Same color bars, same F1-F10 key hints, same blinking red alerts — but underneath it's a deterministic seeded simulation of a company with 5 departments, 3 product types, 3 competitors, and 5 endings. Korean UI, English README, JSON save/load, ~30 minutes per playthrough.

---

## 컨셉 / Concept

`htop`과 100% 동일한 UI (막대 그래프, 트리뷰, 색상, 키바인딩)로 회사 경영 게임을 합니다. 옆에서 보면 "아 IT 운영팀이 서버 모니터링하네" 하는데 정작 게임 중.

The UI is `htop` line-for-line. The data is pure deterministic simulation.

### 메타포 / Metaphor

| 시스템 지표 / System | 회사 자원 / Company resource |
|---|---|
| **CPU 사용률** | 매출 / 마케팅팀 생산성 (Revenue) |
| **메모리 점유** | 재고 / 자산 (Inventory) |
| **스왑** | 부채 / 외부 자금 (Debt) |
| **좀비 프로세스 (Z)** | 퇴사 위기 직원 (Resigning employees) |
| **Load Average** | 시장 수요 / 주문량 (Demand) |
| **nice 값** | 직원 직급 (-20=임원, +19=인턴) |
| **업타임** | 회사 운영 기간 |

---

## 설치 / Installation

```bash
# from PyPI (after first release)
pip install htop-tycoon
htop-tycoon

# from source (development)
git clone https://github.com/sigco3111/htop-tycoon
cd htop-tycoon
uv sync --all-extras --dev
uv run python -m htop_tycoon
```

Requires Python 3.11 or 3.12 (NOT 3.13+; pinned by `requires-python` in `pyproject.toml`).

---

## 사용법 / Usage

```bash
# Default: seed from time, 1 second per game week
python -m htop_tycoon

# Deterministic: same seed → same playthrough (replayable, testable)
python -m htop_tycoon --seed=42 --tick-rate=1

# Fast: 1ms per tick (for testing or fast-forwarding)
python -m htop_tycoon --seed=42 --tick-rate=0.001

# Headless: run 10000 ticks and print final state (for benchmarking)
python -m htop_tycoon --seed=42 --tick-rate=1000 --ticks=10000 --no-autosave

# Load saved game
python -m htop_tycoon --load=~/.local/share/htop-tycoon/save.json
```

CLI flags (frozen for v0.1.0):

| Flag | Type | Default | Description |
|---|---|---|---|
| `--seed INT` | int | `time.time()` | RNG seed (deterministic playthrough) |
| `--tick-rate FLOAT` | float | `balance.time.seconds_per_tick` | Real seconds per game tick (1 tick = 1 game week) |
| `--load PATH` | path | XDG default | Load a saved game from this path |
| `--no-autosave` | flag | False | Disable autosave (for tests) |
| `--dev` | flag | False | Enable Textual dev console |
| `--ending ENDING_TYPE` | str | None | Force-trigger a specific ending at `--ticks` boundary |
| `--ticks N` | int | None | Headless: advance N ticks then exit (no UI) |

---

## 키 바인딩 / Key Bindings

The keys map exactly to `htop`'s real keys but with game-action labels (no `F7 Nice-` / `F8 Nice+` / `F9 Kill` / `F10 Quit`).

| Key | Action (Korean) | English |
|---|---|---|
| `F1` / `h` | 도움말 (이 화면) | Help (this screen) |
| `F2` / `S` | 설정 / 게임 저장 | Setup / Save game |
| `F3` / `/` | 직원 검색 | Search employee |
| `F4` / `\` | 필터 | Filter (name/skill range) |
| `F5` / `t` | 조직도 트리 토글 | Toggle org tree |
| `F6` / `<` `>` | 정렬 사이클 | Cycle sort mode |
| `F7` / `]` | 승진 (+1 tier, 비용: 500₩) | Promote |
| `F8` / `[` | 감봉 (-1 tier, 절약: 300₩) | Demote |
| `F9` / `k` | 해고 (퇴직금 지급) | Fire employee |
| `F10` / `q` | 종료 / 자발적 매각 | Quit / Voluntary sale |
| `u` | 부서 필터 | Filter by department |
| `m` / `s` / `i` | 만족도 / 급여 / 입사순 정렬 | Sort by satisfaction / salary / tenure |
| `p` | 일시정지 / 재생 | Pause / Resume (game clock) |
| `d` | 위임 (자동 관리) | Delegate (auto-manager) |
| `Space` | 직원 태그 | Tag employee |
| `↑` / `↓` | 이동 | Move cursor |
| `Enter` | 선택 | Select |
| `Q` | 모달 닫기 / 게임 종료 | Close modal / Quit game |

---

## 엔딩 / Endings

5 endings, deterministic, mutually exclusive (highest priority wins):

| # | Ending (KO) | Trigger |
|---|---|---|
| 1 | 파산 (Bankruptcy) | `company.cash < balance.money.bankruptcy_cash_floor` (-10,000) |
| 2 | 적대적 인수 (Hostile M&A) | An alive competitor has `cash >= company.market_cap` AND `aggression > 0.9` |
| 3 | 자발적 매각 (Voluntary Sale) | Player triggers sell action AND `cash >= 200,000` |
| 4 | 상장 성공 (IPO) | `market_cap >= 1,000,000` AND `cash > 0` |
| 5 | 비밀 엔딩 (Secret) | All 5 departments unlocked AND all employees at max_skill (10) AND `secret_investor_cleared == True` |

Detailed Korean flavor text for each ending lives in `src/htop_tycoon/data/endings.yaml` and renders in the `EndingScreen` modal at game-over.

---

## 개발 / Development

```bash
# Setup
make install         # uv sync --all-extras --dev

# Quality gates
make test            # uv run pytest -q (full suite, 874 tests)
make lint            # uv run ruff check src/ tests/
make typecheck       # uv run mypy src/ (strict mode)

# Run
make run             # uv run python -m htop_tycoon

# Build
make build           # uv build (wheel + sdist into dist/)

# Release (gated by preconditions)
make release         # asserts clean tree + pyproject version matches the tag
```

Determinism invariant: same seed → identical `state_hash` at every tick. The `tests/test_playthrough.py` test pins this to a frozen literal for `seed=42 → BANKRUPTCY at tick 13` (3 consecutive runs verified).

Coverage: 874 tests across 6 packages (`domain/`, `engine/`, `ui/`, `bindings/`, `persistence/`, `data/`). Targets 80%+ on `domain/ + engine/ + persistence/`.

---

## 기여 / Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the PR process, code style (`ruff` + `mypy --strict`), and development setup.

Issues and PRs welcome at https://github.com/sigco3111/htop-tycoon.

---

## 라이선스 / License

[MIT](LICENSE) — see LICENSE file for full text.

---

## 관련 링크 / Related Links

- [idea-bank #1](https://github.com/sigco3111/idea-bank/blob/main/TUI_Game_Project_Ideas.md) — the source idea
- [Textual](https://textual.textualize.io/) — Python TUI framework powering the UI
- [Rich](https://rich.readthedocs.io/) — terminal rendering used internally

---

> "이거 htop이야 경영 시뮬이야?" — 회사에서 누가 물어봐도 둘 다 맞는 답.
> "Is that htop or a business sim?" — both answers are correct.
