# htop-tycoon v3.0

> **카이로소프트 「게임개발 스토리」 의 htop 스타일 TUI 포팅 + Strategy Manager 자동 위임.**

> A TUI port of Kairosoft's **Game Dev Story**, styled to look like htop, with an automated **Strategy Manager** that runs the company while you watch the metrics.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)

---

## 컨셉 (Concept)

1인 게임 개발 회사를 경영합니다. 직원을 고용하고, 게임을 개발하고, 플랫폼에 출시하고, 시상식에 나가세요. 핵심 차별점은 **Strategy Manager**: 4종 전략(공격적/보수적/균형/장르 집중) 중 하나를 고르면 AI가 일일 의사결정을 자동 수행합니다. 플레이어는 htop UI로 회사를 모니터링하고, 필요할 때만 명령을 오버라이드합니다.

Run a 1-person game development studio: hire staff, develop games, launch on platforms, chase awards. The headline feature is the **Strategy Manager** — pick one of four AI strategies (Aggressive / Conservative / Balanced / Genre-Focus) and watch the AI run day-to-day decisions. The player monitors the company via htop-styled metrics and overrides only when needed.

## htop 메타포 (Metaphor Table)

| htop metric | 게임 의미 (Game meaning) |
|---|---|
| **CPU bars** (per dept) | 부서별 생산성 (활성 직원 × 스킬) |
| **CPU overall** | 회사 전체 생산성 |
| **Memory bar** | 백로그 (개발 중 + 출시된 게임) |
| **Memory swap** | 부채 |
| **Zombie processes (Z)** | 만족도 20% 이하 직원 OR 진척도 0% 정체 게임 |
| **Load Average** | 시장 수요 × 플랫폼 인기 |
| **nice value** | 직원 직급 (`nice_value(job, level)`) |
| **Uptime** | 영업 연차 |
| **4 metric bars** (bottom) | 현재 활성 프로젝트의 품질 4축 (재미/그래픽/사운드/독창성) |
| **Header bar** | 연도 / 현금 / 팬 / 전략 |
| **Footer bar** | F-키 힌트 (한국어) + Auto 모드 표시 |

## 설치 (Install)

```bash
# Requires uv (https://docs.astral.sh/uv/)
git clone https://github.com/sigco3111/htop-tycoon.git
cd htop-tycoon
make install          # uv sync --all-extras --dev
```

## 사용법 (Usage)

```bash
make run              # uv run python -m htop_tycoon
# 또는 (or)
uv run python -m htop_tycoon

# CLI flags (planned for v3.0):
#   --seed <int>       deterministic seed (default: random)
#   --speed <0..4>     initial game speed (default: 1)
#   --headless         run without TUI for QA
```

## 키 바인딩 (Key Bindings)

| Key | 동작 (Action) | English |
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
| `H` | 직원 고용 | Hire |
| `n` | 새 게임 프로젝트 시작 | New game project |
| `g` | 프로젝트 진척 보기 | View game project progress |
| `s` | 전략 선택 모달 | Open StrategyPickerScreen |
| `d` | Auto 모드 토글 | Toggle Auto Manager |
| `a` | 시상식 | Awards |
| `c` | 콘솔 관리 | Console management |
| `Space` | 직원 태그 | Tag employee |
| `Enter` | 선택 | Select |
| `Esc` | 모달 닫기 | Close modal |
| `p` | 일시정지 | Pause |
| `0` | 정지 | Stop time |
| `1` / `2` / `3` | 속도 1x / 2x / 3x | Speed 1x / 2x / 3x |
| `4` | 속도 4x (헤드리스 QA) | Speed 4x (headless QA) |

Speed: `1x` = 1 real-second = 1 game-day (default). `0` pauses time. `4` is reserved for headless QA (the user-facing cap is 3x).

## 엔딩 (Endings)

| # | 이름 (KO) | Name (EN) | 강제 종료? (Forced end?) | 트리거 (Trigger) |
|---|---|---|---|---|
| 1 | 파산 | Bankruptcy | Yes | `cash < -50,000` |
| 2 | 자발적 매각 | Voluntary Sale | Yes (선택) | player triggers sell AND cash ≥ 200,000 |
| 3 | 대박 | Mega Hit | No (계속) | 단일 게임 판매 ≥ 1,000,000 |
| 4 | 명예의 전당 | Hall of Fame | No (계속) | 5+ 게임이 명예의 전당 진입 (평균 평론 ≥ 8.0) |
| 5 | 비밀: 자사 콘솔 + 메가히트 | Secret | No (계속) | 자사 콘솔 출시 AND 그 콘솔에서 게임 100만 판매 |

Soft 엔딩 (3, 4, 5) 은 게임을 끝내지 않고 Legacy Score 패널에 업적으로 기록됩니다.

## 개발 (Development)

```bash
make install     # uv sync --all-extras --dev
make test        # pytest + coverage
make lint        # ruff check
make typecheck   # mypy --strict
make run         # python -m htop_tycoon
make build       # uv build (wheel + sdist)
make release     # precondition check + git tag v3.0.0
make clean       # remove caches, build artifacts
```

## 기여 (Contributing)

기여 가이드는 [CONTRIBUTING.md](CONTRIBUTING.md) 참조. See [CONTRIBUTING.md](CONTRIBUTING.md) for the contributor guide.

스펙 문서: [`docs/superpowers/specs/2026-07-01-htop-tycoon-v3-design.md`](docs/superpowers/specs/2026-07-01-htop-tycoon-v3-design.md).
AI 에이전트용 단축 가이드: [AGENTS.md](AGENTS.md).

## 라이선스 (License)

[MIT](LICENSE)

---

**Inspired by** [Kairosoft Game Dev Story](https://kairosoft.net/game/appli/gamedev.html) • **Powered by** [Textual](https://textual.textualize.io/)