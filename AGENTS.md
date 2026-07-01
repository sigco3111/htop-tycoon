# AGENTS.md — htop-tycoon v3.0

> AI 코딩 에이전트(및 사람 기여자) 대상의 단일 진실 공급원(single source of truth).
> 본 문서는 `docs/superpowers/specs/2026-07-01-htop-tycoon-v3-design.md` 의 핵심만 압축한 요약본이며,
> 충돌 시 **스펙 문서가 우선**한다. 본 파일은 동기화되어야 하지만, 결정적 사양(spec)은 항상 스펙 문서를 참조할 것.

---

## 1. 프로젝트 정체성

- **이름**: htop-tycoon v3.0.0
- **컨셉**: 카이로소프트 「게임개발 스토리」 의 **TUI 포팅 + Strategy Manager 자동 위임**.
- **UI 메타포**: htop 화면처럼 보인다 (CPU/메모리/스왑/좀비/Load/nice/업타임/4축 바).
- **언어**: 게임 내 UI는 **한국어 기본**, README/문서만 영어 허용. i18n 프레임워크 없음.

## 2. 범위 캡(Scope Cap) — 절대 초과 금지

- 부서 **5개** (경영/기획/개발/아트/사운드)
- 기본 직종 **6개** + prestige **1개** (HW Engineer; 비밀 엔딩 후 해금)
  - Producer / Game Designer / Programmer / Graphic Artist / Sound Creator / Hacker / HW Engineer
- 엔딩 **5개** (파산/자발적 매각/대박/명예의 전당/비밀)
- 활성 플랫폼 최대 **4개** (PC 1 + 콘솔 최대 3, 후반 자사 콘솔 1)
- 장르 최대 **12개**, 테마 **30개 이상**
- 품질 축 **4개**: 재미 / 그래픽 / 사운드 / 독창성 (기술력 축 없음)

## 3. 시간 스케일

- **1초 = 1 게임 일** (기본 1x 속도)
- 키 `0`: 정지(속도 0) / `1`: 1x / `2`: 2x / `3`: 3x / `4`: 4x (헤드리스 QA 전용; 사용자 노출 캡은 3x)
- 한 게임 해(年) = 365 게임 일

## 4. Strategy Manager (★ 차별화 기능)

- 4종 전략: **Aggressive / Conservative / Balanced / Genre-Focus**
- 공통 인터페이스 `Strategy.decide(state, rng) -> list[PlannedAction]`
- 키 `s`: 전략 선택 모달, 키 `d`: Auto 모드 on/off 토글
- 일일 결정 액션 상한 = `balance.ai.max_actions_per_day` (기본 10)
- 수동 명령은 항상 자동 결정보다 우선

## 5. 핵심 불변식(Critical Invariants)

1. **GameState 단일 경계**: 직렬화/스냅샷/이벤트는 모두 `GameState` 를 통해서만.
2. **엔진은 순수(pure)**: I/O / UI / clock 접근 금지. 입력은 state, 출력은 `(new_state, [events])`.
3. **모든 RNG는 `GameRNG(seed)` 경유**: 코드 어디서도 `random.*` 직접 호출 금지 (테스트의 결정성 깨짐).
4. **매직 넘버 금지**: 게임 수치는 모두 `data/balance.yaml` 에서 로드. 소스 코드 리터럴 금지.
5. **`CORRUPTION_RECOVERY_SEED = 0`**: 시드 저장 파싱 실패 시 새 게임 생성에 절대 `time.time()` 금지.
6. **JSON only**: SQLite/DB 없음. 원자적 쓰기 + 백업 + 마이그레이션 체인.
7. **엔진 → UI 단방향**: `EventBus` 통해서만. UI가 엔진을 직접 호출하지 않음.
8. **키 바인딩 충돌 시 부팅 실패**: `bindings.registry` 가 앱 부팅 시점에 raise.

## 6. 디렉토리 구조(목표)

```
src/htop_tycoon/
  __init__.py
  __main__.py          # CLI entry
  cli_parser.py        # 인자 파싱
  domain/              # 순수 dataclass (GameState, Employee, ...)
  engine/              # 순수 로직 (tick, actions, ...)
    strategy/          # Strategy 인터페이스 + 4 구현 (★ 핵심)
  ui/                  # Textual 앱/스크린/위젯
  bindings/            # 키 레지스트리
  persistence/         # 직렬화/마이그레이션
  data/                # balance.yaml, genres.yaml, ...
tests/
  test_*.py            # pytest
```

## 7. 결정성 회귀 테스트

`seed=42` 기준 3개 시점의 state 해시 동결:
- day 100 / day 1000 / day 3650 (10년)

위 해시는 절대 깨지면 안 된다 — 깨지면 회귀 버그.

## 8. 안티패턴 (절대 하지 말 것)

- 멀티플레이어, 온라인, 리더보드, 계정 — 없음
- `psutil` 등 실제 시스템 모니터링 — 없음
- 사운드, 모바일, 웹 GUI — 없음
- i18n 프레임워크 — 없음
- SQLite/DB — 없음 (JSON only)
- **이모지 — 소스/문서/커밋 어디에도 금지**
- 매직 넘버 — `balance.yaml` 외부 금지
- bare `random.*` — `engine/rng.py` 외부 금지
- 멀티 직렬화 경계 — `GameState` 단일만
- M&A 메커닉, 주식/증권 시뮬, 명시적 대출, 마케팅 캠페인 시스템, R&D 테크 트리 — 모두 v3.0 범위 밖

## 9. 성공 기준 (v3.0 완료)

1. §7.7 7개 릴리스 게이트 모두 통과
2. `seed=42` 30분 플레이 → {대박, 명예의 전당, 파산, 자발적 매각} 중 하나 도달 (3회 재현 가능)
3. 4개 전략이 동일 시드 10년 플레이에서 서로 다른 의사결정 보임
4. macOS Terminal / iTerm2 / GNOME / Windows Terminal 에서 한국어 깨짐 없음
5. 비밀 엔딩 60분 내 도달 가능
6. Legacy Score 패널이 저장/로드 사이클에서 업적 정확히 추적

---

상세 결정·트레이드오프·이유는 언제나 **스펙 문서**(`docs/superpowers/specs/2026-07-01-htop-tycoon-v3-design.md`)를 정본으로 삼을 것.