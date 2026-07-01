# htop-tycoon v3.0 — Game Dev Story TUI Design Spec

> **Status**: APPROVED (sections 1-4 user-approved on 2026-07-01)
> **Author**: brainstorming session with user
> **Project reset**: full code reset; concept pivots from generic business sim to Game Dev Story port + Strategy Manager delegation

---

## 1. Concept & Scope

### 1.1 What we are building

**htop-tycoon v3.0**: a TUI port of Kairosoft's **Game Dev Story** (게임개발 스토리), styled to look like htop. The player runs a 1-person game development company: hire employees, develop games, sell on platforms, attend awards, and grow.

**The killer feature**: a strengthened **Strategy Manager** delegation system. The player picks a high-level strategy (Aggressive / Conservative / Balanced / Genre-Focus), and an AI executes day-to-day decisions automatically (hire, fire, train, start games, assign employees, choose genres). The player monitors via htop UI and overrides when needed.

### 1.2 Why we are building it

The v0.1.0 / v0.2.0 implementation had four concrete failures:
1. Balance (too easy/hard, endings unreachable)
2. Core mechanics (regimes/focus/AI didn't work as intended)
3. UI/UX misalignment (htop metaphor didn't map cleanly to game state)
4. Rules incomplete/misdesigned

A full reset was chosen because: system-level complexity caused the failures (5 depts × 3 products × 3 competitors × 5 endings × 4 regimes × 14 focus types × AI manager = 14+ interacting systems, each individually unbalanceable).

### 1.3 Scope cap (hard limits)

- **5 departments** (경영/기획/개발/아트/사운드)
- **6 job types** (Producer / Game Designer / Programmer / Graphic Artist / Sound Creator / Hacker)
- **5 endings** (max 5 — see §1.4)
- **Max 4 active platforms** (1 PC + up to 3 consoles + own console in late game)
- **Max 12 genres**, **30+ themes** (for combination discovery — concrete list in §2.7)
- **4 quality axes**: 재미 / 그래픽 / 사운드 / 독창성 (no "tech level" axis)
- **6 base jobs + 1 prestige job** (HW Engineer, unlocked after Secret ending — see §2.5)
- **Time scale**: 1 real-second = 1 game-day at 1x speed; user-controllable **1x–4x** via keys 1/2/3/4 (with key 4 reserved for headless QA); `0` pauses time (see §4.1)

Any expansion requires a plan revision and a wave note.

### 1.4 The 5 endings

| # | Name (KO) | Name (EN) | Forced end? | Trigger |
|---|---|---|---|---|
| 1 | 파산 | Bankruptcy | **Yes** | `company.cash < balance.money.bankruptcy_floor` (-50,000) |
| 2 | 자발적 매각 | Voluntary Sale | **Yes** (player choice) | player triggers sell action AND cash ≥ 200,000 |
| 3 | 대박 | Mega Hit | **No** (continue) | a single game sells ≥ 1,000,000 copies |
| 4 | 명예의 전당 | Hall of Fame | **No** (continue) | 5+ games enter Hall of Fame (avg critic ≥ 8.0) |
| 5 | 비밀: 자사 콘솔 + 메가히트 | Secret: Own Console + Mega Hit | **No** (continue) | own console released AND a game sells ≥ 1M on it |

**Soft endings** (3, 4, 5) do NOT end the game. They unlock achievements, which show on a Legacy Score panel. Player continues indefinitely until Bankruptcy / Voluntary Sale.

### 1.5 Bonus challenges (achievements, tracked on Legacy Score)

- "10년 연속 흑자" — 10 in-game years in profit
- "장르 20개 출시" — release games in 20 distinct genres
- "직원 50명 보유" — employ 50 people at once
- "연봉 100만G 직원 키우기" — train an employee whose monthly salary exceeds 1,000,000
- "4개 콘솔 동시 보유" — own licenses for 4 consoles at once
- "비밀 엔딩 + 명예의 전당 동시" — both Secret and Hall of Fame in one run
- Others TBD during implementation

---

## 2. Game Mechanics (Game Dev Story port)

### 2.1 Departments and jobs

Each game has 4 quality axes. Department contributions:

| Department | Job types | 재미 | 그래픽 | 사운드 | 독창성 | Fans |
|---|---|---|---|---|---|---|
| 기획 (Planning) | Game Designer, Producer | ✓ | | | ✓ | |
| 개발 (Development) | Programmer, Hacker | ✓ (2x weight) | | | | |
| 아트 (Art) | Graphic Artist | | ✓ | | | |
| 사운드 (Sound) | Sound Creator | | | ✓ | | |
| 경영 (Management) | Producer | | | | | ✓ |

- When both 기획 and 개발 contribute to 재미, the higher contribution wins (`max(기획_기여, 개발_기여 × 2)`).
- Other axes use single-source contribution.
- Department unlocking: start with 경영 + 기획 unlocked; 나머지 3개는 게임 진행 중 조건 만족 시 해금.

### 2.2 Game development loop

For each in-progress game project:
1. Player (or Strategy Manager) picks **genre** (e.g., RPG) and **direction/theme** (e.g., time travel).
2. Player assigns 1+ employees to the project.
3. Each game-day: `progress += sum(employee.skill * dept_bonus)`.
4. At progress milestones (25%, 50%, 75%): player (or AI) assigns a **special task** (특무) to one employee for a bonus.
5. At progress 100%: game completes.
6. 4 critics each score 0–10 → average → final rating.
7. Game launches on a chosen platform.
8. Sales accumulate based on `quality × platform_popularity × fan_base`.

### 2.3 Platforms and consoles

| Platform | License needed? | Royalty | Sales | Lifecycle |
|---|---|---|---|---|
| PC | No | 0% | Low | Permanent |
| 콘솔 A (e.g., "플박") | Yes | 15% | High | `consoles.yaml` config: `peak_year: 3`, `decline_rate: 0.15`, `discontinue_year: 8` |
| 콘솔 B | Yes | 15% | High | (per-console config) |
| 콘솔 C | Yes | 15% | High | (per-console config) |
| 자사 콘솔 (Own Console) | N/A (self) | 0% | Very High | Requires HW Engineer; permanent |

Console lifecycle: each console has a popularity curve. When popularity hits 0, the console is **discontinued** — back catalog still sells (decay rate applies) but new games cannot be released on it.

**Mega Hit / Secret ending feasibility**: every ending must remain reachable under default balance. The Wave 1 frozen-hash tests verify that seed=42 reaches Mega Hit on at least one console within 10 years.

### 2.4 Awards and game shows

All award values live in `data/balance.yaml`:

```yaml
awards:
  year_end:
    first_prize: 200000      # 1등 상금 (G)
    second_prize: 100000
    third_prize: 50000
    trash_penalty: 100000    # "쓰레기 게임 상" 벌금 (G)
  game_show:
    fan_boost_pct: 0.50      # +50% 팬 증가
    duration_days: 180       # 6개월 (게임 일)
    participation_cost: 20000
  eligibility:
    year_end_min_score: 5.0  # 연말 시상식 대상 최소 평점
    trash_max_score: 4.0     # 이 점수 이하면 "최악의 게임" 후보
```

- **Year-end Awards Ceremony**: games released that year with avg critic score ≥ `year_end_min_score` are eligible. Top score wins `first_prize`, second wins `second_prize`, third wins `third_prize`. Worst eligible game (avg < `trash_max_score`) gets `trash_penalty`.
- **Annual Game Show**: player can run a booth once per year. Cost: `participation_cost`. Effect: +`fan_boost_pct` × current_fans added, lasting `duration_days`.

### 2.5 Employee career system

- Each employee has 5 levels per job.
- Leveling up increases skill but also salary (+20% per level).
- Changing job (e.g., Programmer → Game Designer): salary multiplies by 1.2.
- Max 6 jobs × 5 levels = max 24 level-ups → salary × 79.4.
- Late-game prestige: train a max-level employee to **HW Engineer** (only available after reaching Secret ending condition once).

### 2.6 Fan economy

Fans accumulate via game sales. The formula and key constants:

```yaml
fans:
  per_sale_factor: 1.0       # copies_sold → fans (linear)
  game_show_boost: 0.50     # pct added during game show effect
  decay_per_quarter_pct: 0.02  # 2% decay per in-game quarter
  base_fan_factor: 0.001     # fan_base multiplier in sales formula
```

Sales formula (§2.2 step 8) becomes:
```
sales_revenue = (quality_avg / 10) × platform_popularity × (1 + fans × base_fan_factor)
```

Sales copies → fans: `fans += copies_sold × per_sale_factor` (per release).
Decay applies every 90 in-game days.

### 2.7 Starter genre/theme list (concrete for v3.0)

Implemented in `data/genres.yaml` and `data/themes.yaml`. Korean labels in UI.

**12 genres**:
1. RPG (알피지)
2. Action (액션)
3. Simulation (시뮬레이션)
4. Adventure (어드벤처)
5. Puzzle (퍼즐)
6. Strategy (전략)
7. Sports (스포츠)
8. Rhythm (리듬)
9. Fighting (격투)
10. Horror (호러)
11. Educational (교육)
12. Online (온라인)

**30 themes** (subset; full list in implementation):
- 판타지 / SF / 현대 / 역사 / 미래 / 동화 / 무협 / 학원 / 요괴 / 좀비 / 우주 / 잠입 / 해적 / 사무라이 / 요리 / 음악 / 운동 / 패션 / 연애 / 추리 / 법정 / 시간여행 / 마법 / 로봇 / 동물 / 의학 / 자동차 / 비행 / 주식 / 게임

**Combo bonuses** (defined in `data/combos.yaml`, examples):
- 액션 + 닌자 → "Mega Hit" 후보 (sales × 2)
- 리듬 + 댄스 → sales × 1.5
- RPG + 송이버섯 → sales × 1.5
- 시뮬 + 편의점 → sales × 1.3
- (총 12+ combo 정의, 구현 시 확정)

### 2.8 Console lifecycle parameters

Each console in `data/consoles.yaml` has:
```yaml
- id: console_a
  name_ko: "플박"
  name_en: "PlayBox"
  release_year: 1
  peak_year: 3
  decline_rate: 0.15
  discontinue_year: 8
  base_popularity: 1.5
```

3 default consoles defined. Players license each at a cost (varies per console).

---

## 3. Strategy Manager (delegation)

### 3.1 Strategy types

| Strategy | Auto-hire | Auto-fire | Training | Game starts | Genre choice |
|---|---|---|---|---|---|
| **공격적 (Aggressive)** | Yes (cash > 30K) | No (keep all) | Minimal | Immediately if no active project | High-risk high-reward combos |
| **보수적 (Conservative)** | Only if cash > 100K | Yes (low performers) | Heavy before assign | Only if cash > 50K | Safe, established combos |
| **균형 (Balanced)** | Yes (cash > 50K) | Yes (very low) | Moderate | If no project + cash > 20K | Mix of safe + occasional risk |
| **장르특화 (Genre Focus)** | Yes (within budget) | No | Focused on chosen genre | Continuously | Spam chosen genre for combo bonuses |

### 3.2 Decision cycle and interface

Each game-day tick:
1. Read current state.
2. Call `strategy.decide(state, rng) -> list[PlannedAction]`.
3. Execute each `PlannedAction` via `engine.actions.py` (sorted by `priority` desc, then `kind` order).
4. Emit events for each executed action.
5. Show in `StrategyStatus` widget what the AI did today.

#### 3.2.1 `PlannedAction` schema (concrete)

```python
from dataclasses import dataclass
from typing import Any, Literal
from htop_tycoon.domain.ids import EntityId

ActionKind = Literal[
    "HIRE",          # params: {dept_id: DeptId, job_type: JobType}
    "FIRE",          # params: {employee_id: EmployeeId, reason: str}
    "TRAIN",         # params: {employee_id: EmployeeId, target_level: int}
    "START_GAME",    # params: {genre_id: str, theme_id: str, platform_id: PlatformId}
    "ASSIGN",        # params: {employee_id: EmployeeId, project_id: ProjectId}
    "PROMOTE",       # params: {employee_id: EmployeeId}
    "DEMOTE",        # params: {employee_id: EmployeeId}
    "CHANGE_JOB",    # params: {employee_id: EmployeeId, new_job: JobType}
    "NOTHING",       # no params; explicit "skip this day" marker
]

@dataclass(frozen=True)
class PlannedAction:
    kind: ActionKind
    target_id: EntityId | None
    params: dict[str, Any]
    priority: int  # higher = earlier; range 0-100
```

A strategy returns a list sorted by `priority` desc. The engine executes up to `balance.ai.max_actions_per_day` actions per day.

### 3.2.2 `Strategy` interface (concrete)

```python
from abc import ABC, abstractmethod

class Strategy(ABC):
    name: str  # "aggressive" | "conservative" | "balanced" | "genre_focus"

    @abstractmethod
    def decide(self, state: GameState, rng: GameRNG) -> list[PlannedAction]:
        """Return the day's planned actions, sorted by priority desc."""

    def post_execute(self, state: GameState, executed: list[PlannedAction]) -> None:
        """Optional hook called after actions are applied. Default: no-op."""
```

### 3.2.3 File layout (concrete)

```
src/htop_tycoon/engine/strategy/
├── __init__.py            # exports StrategyRegistry
├── types.py               # ActionKind, PlannedAction
├── base.py                # Strategy ABC + StrategyRegistry
├── aggressive.py
├── conservative.py
├── balanced.py
└── genre_focus.py
```

### 3.3 Override

- **Auto toggle key**: `'d'` — toggles Auto mode on/off (binary flag).
- **Strategy picker key**: `'s'` — opens `StrategyPickerScreen` modal (one-time selection: pick one of the 4 strategies).
- When Auto is off, no auto decisions happen; manual play resumes.
- When Auto is on, player can still issue manual commands — they take priority and are not undone by the AI.

### 3.4 Player visibility

The htop UI shows what the AI is doing in real time via the `StrategyStatus` widget:
- "AI: 직원 김코딩 해고함 (사유: 생산성 30% 이하)"
- "AI: 신규 프로젝트 시작 — '시간여행 RPG' (장르: RPG, 방향: 시간여행)"
- "AI: 박아트 → 해커 직업 변경 제안 (연봉 ×1.2)"

---

## 4. htop UI Mapping

| htop metric | Maps to |
|---|---|
| **CPU bars** (per dept) | Per-department productivity / active employees × skill |
| **CPU overall** | Total company productivity |
| **Memory bar** | Backlog (in-progress games + released games) |
| **Memory swap** | Debt |
| **Zombie processes (Z)** | Employees with satisfaction ≤ 20% OR games stuck at 0% progress |
| **Load Average** | Market demand × platform popularity |
| **nice value** | Employee rank (see §4.1.1 for compression algorithm) |
| **Uptime** | In-game years in business |
| **4 metric bars** (bottom) | Game quality axes: 재미 / 그래픽 / 사운드 / 독창성 (for currently active project) |
| **Header bar** | Year / Cash / Fans / Strategy indicator |
| **Footer bar** | F-key hints (Korean) + Auto mode indicator |

### 4.1 Key bindings (htop-style)

Single-key aliases follow htop convention: lowercase = primary action, uppercase (Shift) = alternative action.

| Key | Action (Korean) | English |
|---|---|---|
| `F1` / `h` | 도움말 | Help |
| `F2` / `S` | 저장 | Save |
| `F3` / `/` | 직원 검색 | Search employee |
| `F4` / `\` | 필터 | Filter |
| `F5` / `t` | 부서 트리 토글 | Toggle dept tree |
| `F6` / `<` `>` | 정렬 사이클 | Sort cycle |
| `F7` / `]` | 직원 승진 | Promote |
| `F8` / `[` | 직원 감봉 | Demote |
| `F9` / `k` | 직원 해고 | Fire |
| `F10` / `q` | 종료 / 매각 | Quit / Sell |
| `H` (Shift+h) | 직원 고용 | Hire (single key — `h` reserved for help) |
| `n` | 새 게임 프로젝트 시작 | New game project |
| `g` | 게임 프로젝트 진행 보기 | View game project progress |
| `s` | 전략 선택 (모달) | Open StrategyPickerScreen |
| `d` | Auto 모드 토글 (on/off) | Toggle Auto Manager |
| `a` | 시상식 | Awards |
| `c` | 콘솔 관리 | Console management |
| `Space` | 직원 태그 | Tag employee |
| `↑` `↓` | 이동 | Move cursor |
| `Enter` | 선택 | Select |
| `Esc` | 모달 닫기 | Close modal |
| `p` | 일시정지 | Pause |
| `0` | 정지 (속도 0) | Stop time |
| `1` | 속도 1x (1초=1일) | Speed 1x |
| `2` | 속도 2x (1초=2일) | Speed 2x |
| `3` | 속도 3x (1초=3일) | Speed 3x |
| `4` | 속도 4x (1초=4일, headless QA) | Speed 4x |

**Speed clarification**: `1x` = 1 real-second = 1 game-day (default). Higher numbers = faster game-time per real second. So `3x` advances 3 game-days per real second. `0` pauses time entirely. Key `4` is for headless QA runs (4 days/sec); the user-facing cap is 3x.

#### 4.1.1 nice value compression algorithm

Each employee has a 2-tuple `(job_index, level)` where:
- `job_index ∈ {0..5}` corresponds to `[Producer, Game Designer, Programmer, Graphic Artist, Sound Creator, Hacker]`
- `level ∈ {1..5}`

The nice value is computed as:

```python
def nice_value(job_index: int, level: int) -> int:
    """Map (job, level) → nice value in [-20, +19]."""
    # Higher job_index + higher level = lower nice (more senior)
    rank = job_index * 5 + (level - 1)  # 0..29
    return clamp(20 - rank, -20, 19)
```

So:
- `Producer Lv5` (job_index=0, level=5): rank=4 → nice=+16 (most senior)
- `Hacker Lv1` (job_index=5, level=1): rank=25 → nice=-5 (most junior)
- New hires (default `Programmer Lv1`): rank=10 → nice=+10

Negative nice values (−1 to −20) reserved for HW Engineer (post-Secret prestige job).

---

## 5. Architecture & Data Flow

### 5.1 Package structure

- `domain/` — pure dataclasses (GameState, Employee, GameProject, Console, Market, Event, Ending)
- `engine/` — pure logic (tick, actions, game_dev, sales, critic, award, endings, rng)
- `engine/strategy/` — Strategy interface + 4 implementations (★ new) — see §3.2.3 for file layout
- `ui/` — Textual app, screens, widgets (including `StrategyStatus` widget ★ new)
- `bindings/` — key registry
- `persistence/` — serialize, deserialize, migration
- `data/` — balance.yaml, genres.yaml, themes.yaml, consoles.yaml, combos.yaml, achievements.yaml

### 5.2 State flow

```
Player Input
    → bindings.registry (key → action)
    → app.dispatch_action
    → engine.actions.X (pure function)
    → returns (new_state, [events])
    → event bus emits
    → UI re-renders from snapshot

Timer tick (real time, configurable 0~3x)
    → engine.tick.run_day
        ├── Strategy Manager decides (★)
        ├── Execute planned actions
        ├── Advance in-progress games
        ├── Market dynamics
        ├── End-of-day events
        └── Endings check
    → returns (new_state, [events])
    → event bus emits
    → UI re-renders
```

### 5.3 Core principles

- **GameState**: single serialization boundary, immutable update via `dataclasses.replace`.
- **Engine**: pure functions only. No I/O, no UI.
- **Strategy Manager**: 4 strategies implement a common `Strategy` interface (`decide(state, rng) -> list[PlannedAction]`).
- **Determinism**: all RNG flows through `GameRNG(seed)`. Same seed → identical state hash.
- **Save/load**: JSON, atomic write, backup, schema migration.

### 5.4 Tech stack

- Python 3.11 / 3.12 (NOT 3.13+, pinned in pyproject.toml)
- Textual ≥0.86
- Rich ≥13
- pyyaml ≥6
- pytest + pytest-asyncio + textual Pilot
- ruff + mypy --strict

---

## 6. Error Handling

| Situation | Handling |
|---|---|
| `hire` with insufficient budget | action returns `(state, [HireFailedEvent])` → UI toast |
| `start_game` with no dept unlocked | returns failure event → UI modal |
| `rng.sample` on empty dataset | forced fallback to single safe value |
| Strategy decision infinite loop | capped at `balance.ai.max_actions_per_day` (default 10) |
| Save JSON parse failure | try backup; if both fail, `CORRUPTION_RECOVERY_SEED=0` new game + user notification |
| Save SCHEMA_VERSION mismatch | `persistence.migration.upgrade_vN_to_vN+1` chain |
| Console discontinued mid-game-project | platform_status="dead" → sales=0 on new titles; back catalog unaffected |
| Employee satisfaction hits 0 | auto-fired by engine, dept unlocked count may drop |
| Game stuck at 0% progress | becomes "zombie game" (visible in UI) if `days_since_start >= balance.zombie.stuck_threshold_days` (default 7); no auto-recovery |
| Key binding collision | `bindings.registry` raises at app boot — fail fast |

---

## 7. Testing Strategy

### 7.1 Categories

| Type | Tool | Target | Goal |
|---|---|---|---|
| Unit | pytest | `domain/*`, `engine/*` | 90%+ line coverage |
| Integration | pytest | `engine/*` + `persistence/*` | 100% scenario coverage |
| UI Pilot | textual.Pilot | `ui/*` (5 required scenarios) | 5 scenarios pass |
| Determinism | pytest | all RNG flows | seed-pinned state hashes |
| Snapshot | syrupy | GameState JSON | schema evolution |

### 7.2 Coverage targets

- `domain/ + engine/ + persistence/`: **80%+** (CI enforced)
- `engine/strategy/` (delegation): **100%** (it's the differentiator)
- `ui/`: pass 5 Pilot scenarios (coverage secondary)

### 7.3 Determinism regression tests

Three frozen state hashes pinned at:
- `seed=42 → day 100`
- `seed=42 → day 1000`
- `seed=42 → day 3650` (10 in-game years)

**Capture procedure** (Wave 1 implementation):
1. Implement engine + persistence with no frozen hashes yet.
2. Run `python -m htop_tycoon --seed=42 --tick-rate=0.01 --ticks=N` for each N.
3. Capture `state.compute_hash()` outputs.
4. Commit literals to `tests/fixtures/frozen_hashes.yaml`.
5. Run 3 consecutive CI runs; if all match, gate is locked.
6. Release gate 7 (§7.7) requires all 3 hashes stable.

### 7.4 Pilot UI scenarios (5 required)

1. `startup_render` — app boots, main screen renders
2. `strategy_picker` — press `s` → StrategyPickerScreen shows 4 options
3. `hire_action` — press `H` (Shift+h) → dept picker → employee added → metric updates
4. `start_game_action` — press `n` → genre+direction pick → game starts → progress shown
5. `save_load_roundtrip` — press `S` → save → restart → load → identical state

### 7.5 CI matrix

- OS: ubuntu-latest, macos-latest, windows-latest
- Python: 3.11, 3.12
- Pilot: ubuntu + macos only (Windows = pytest only)
- Lint: ruff (all OS)
- Type check: mypy --strict (all OS)

### 7.6 Manual QA artifacts (`.omo/evidence/`)

- `manual_qa_short.txt` — short playthrough, 3 screenshots (≈7.5 min wall-clock at 4x; see §7.7)
- `manual_qa_strategies.txt` — 4 strategies × 10 years each, comparison
- `manual_qa_cjk.txt` — Korean rendering check
- `manual_qa_console_death.txt` — console discontinuation handling

### 7.7 Concrete QA generation steps

For each artifact, the steps are reproducible from a single command:

| Artifact | Command | Output |
|---|---|---|
| `manual_qa_short.txt` | `python -m htop_tycoon --seed=42 --tick-rate=4 --ticks=1800` (with `--headless --no-autosave`) + manual UI screenshots at t=600, t=1200, t=1800 | terminal log + 3 PNGs |
| `manual_qa_strategies.txt` | `bash scripts/qa_strategy_compare.sh 42 10` — runs 4 strategies × 10 years (3650 ticks each) at 4x speed, saves log per strategy | 4 log files + comparison table |
| `manual_qa_cjk.txt` | `python -m htop_tycoon --seed=42 --ticks=100 --dev` then `grep -P "[\\uAC00-\\uD7AF]" out.log` — verifies Korean chars render | log + grep result |
| `manual_qa_console_death.txt` | `python -m htop_tycoon --seed=42 --ticks=3000 --force-console-discontinue=8` — runs to year 8+ | log + state.json snapshot |

### 7.8 Release gate

`make release` requires:
1. `git status --porcelain` empty
2. `pyproject.toml` version matches git tag
3. `make test` all green
4. `make lint` clean
5. `make typecheck` clean
6. Short full-playthrough manual QA passes (see §7.7)
7. All 3 frozen state hashes match (see §7.3)

---

## 8. Reset Procedure

Because we are doing a full code reset, the implementation phase begins with:

### 8.1 Git cleanup

1. Delete stale branches:
   - `feat/htop-tycoon-v0.1.0` (merged into main; safe to delete)
   - `feat/htop-tycoon-v0.2.0-regimes-focus` (merged into main; safe to delete)
   - `fix/orgtree-dict-shape`, `fix/orgtree-dict-shape-2`, `fix/orgtree-shape-only` (merged; safe to delete)
2. Remove the secondary worktree: `/Users/hjshin/Desktop/project/work/ai-driven-dev/htop-tycoon-v0.2.0`
3. Drop the `wip-pre-v0.2.0` stash
4. **Tag policy**: `v0.1.0` is the only release tag and remains on its commit (no rewrite). v0.2.0 work was merged to `main` via PR but never tagged; no tag exists to preserve. v3.0.0 tag will be added after PR merge + `make release` preconditions pass.

### 8.2 File removal (full reset)

Remove:
- All of `src/htop_tycoon/*` (engine, ui, domain, bindings, persistence, data)
- All of `tests/*`
- `docs/superpowers/specs/2026-06-29-delegation-design.md` (obsolete)
- `CHANGELOG.md` (rewrite)
- `AGENTS.md` (rewrite)
- `.omo/plans/htop-tycoon.md` (rewrite)
- `.omo/drafts/htop-tycoon.md` (rewrite)
- `.omo/evidence/*` (50+ stale task files)
- `.github/workflows/ci.yml` (rewrite for v3 matrix)
- `.github/workflows/release.yml` (rewrite for v3 release)
- `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`

Keep:
- `LICENSE`, `CONTRIBUTING.md` (general docs, valid for any Python project)
- `.git/`, `.gitignore` (preserve history and config)
- `pyproject.toml` skeleton (will be edited for v3.0.0)
- `Makefile` (will be edited)

### 8.3 New files (initial commit)

After cleanup, the first commit will include:
- `LICENSE`
- `CONTRIBUTING.md`
- `.gitignore` (updated to ignore .venv, caches, .omo)
- `pyproject.toml` (name=htop-tycoon, version=3.0.0, deps)
- `Makefile` (test/lint/typecheck/run/build/release targets)
- `README.md` (new Korean+English, Game Dev Story TUI pitch)
- `AGENTS.md` (rewrite: reflects v3.0.0 reality)
- `CHANGELOG.md` (v3.0.0 entry: full reset, Game Dev Story port, Strategy Manager)
- `.github/workflows/ci.yml` (v3 matrix: ubuntu + macos for Pilot, windows for pytest-only, Python 3.11/3.12, ruff + mypy --strict jobs)
- `.github/workflows/release.yml` (v3 release: build wheel + sdist, attach to GitHub Release)
- `.omo/plans/htop-tycoon.md` (new plan, will be written by `writing-plans` skill)
- `.omo/drafts/htop-tycoon.md` (interview record)
- `docs/superpowers/specs/2026-07-01-htop-tycoon-v3-design.md` (this file)

### 8.4 Bump version

`pyproject.toml`: `version = "0.2.0"` → `version = "3.0.0"`

---

## 9. Anti-patterns (carried forward + new)

Carried from previous project:
- No multiplayer, online, leaderboards, accounts
- No real system monitoring (no `psutil`)
- No sound, no mobile, no web GUI
- No i18n framework (Korean only; English only in README)
- No SQLite / database (JSON only)
- No emoji in source, docs, commits
- No magic numbers (all in `balance.yaml`)
- No bare `random.*` outside `engine/rng.py`
- Single serialization boundary: `GameState`
- Engine → UI is one-way via EventBus
- `CORRUPTION_RECOVERY_SEED = 0` (never derived from real time)

New for v3.0:
- No M&A mechanics (replaced with sell-your-own-company ending)
- No "real" stock/equity simulation (replaced with simple cash + fans)
- No "loans / banking" system (debt comes from overspending, not explicit loans)
- No "marketing campaigns" as a system (covered by game shows + Strategy Manager auto)
- No "R&D tech tree" (gameplay unlocks via genre/theme discovery, not tech tree)

---

## 10. Out of scope (v3.0)

These are explicitly **not** in v3.0:
- Modding / replay framework
- Multiplayer / online leaderboards
- Difficulty modifiers
- Achievements beyond the 7 listed in §1.5 (others are TBD but not in v3.0 scope)
- Tutorial branches (player learns by playing, like the original Game Dev Story)
- Internationalization framework
- Mobile / web GUI / sound
- Loans / stock simulation
- Marketing campaigns system
- R&D tech trees
- Game-show-as-mini-game (game show is just a cash fan-boost button, not a minigame)
- Hardware-engineer unlock beyond Secret ending (Secret ending grants the unlock as a one-time bonus; further gameplay with HW Engineer is post-v3.0 scope)

---

## 11. Success criteria

v3.0 is done when:
1. All 7 release gates in §7.7 pass.
2. A 30-minute playthrough starting with seed=42 reaches one of {Mega Hit, Hall of Fame, Bankruptcy, Voluntary Sale}. The playthrough is reproducible across 3 runs (same seed = same final state).
3. All 4 Strategy types are demonstrably different in their decisions when run side-by-side on the same seed for 10 years.
4. Korean UI renders cleanly on macOS Terminal, iTerm2, GNOME Terminal, Windows Terminal. No garbled CJK.
5. Player can complete a Secret ending run within ~60 minutes.
6. Legacy Score panel correctly tracks achievements across save/load cycles.

---

## 12. Open questions (for implementation phase)

These are NOT blockers for design but should be resolved in the implementation plan:

1. Exact YAML schema for `genres.yaml` and `themes.yaml` (currently 12 genres and 30+ themes are planned; specific list TBD).
2. Specific "daboa" combination bonuses (Game Dev Story has specific combos like "Action + Ninja = Mega Hit"); TBD in implementation.
3. Console names and exact popularity curves (TBD; will use real-world-inspired parodies).
4. Achievement list — 7 listed in §1.5; others TBD.
5. Critic personality definitions (4 critics, each with their own taste biases; TBD in implementation).

---

## 13. References

- Original game: [Kairosoft Game Dev Story](https://kairosoft.net/game/appli/gamedev.html)
- Korean wiki: [나무위키 게임개발 스토리](https://namu.wiki/w/%EA%B2%8C%EC%9E%84%EA%B0%9C%EB%B0%9C%20%EC%8A%A4%ED%86%A0%EB%A6%AC)
- Textual framework: [textual.textualize.io](https://textual.textualize.io/)
- Determinism reference: previous htop-tycoon v0.1.0/v0.2.0 frozen-hash tests (kept in git history)

---

**End of design spec. Approved for implementation planning.**