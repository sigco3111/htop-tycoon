# 💼 htop-tycoon — htop으로 회사 경영하는 TUI 게임

> **화면 캡처 한 장만 봐도 서버 모니터링 같지만, 사실 회사 경영 게임.**
> CPU는 매출, 메모리는 재고, 좀비 프로세스는 퇴사 위기 직원.

<p align="left">
  <a href="https://github.com/sigco3111/htop-tycoon/blob/main/LICENSE"><img src="https://img.shields.io/github/license/sigco3111/htop-tycoon?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/sigco3111/htop-tycoon/stargazers"><img src="https://img.shields.io/github/stars/sigco3111/htop-tycoon?style=for-the-badge" alt="Stars"></a>
  <a href="https://github.com/sigco3111/htop-tycoon/issues"><img src="https://img.shields.io/github/issues/sigco3111/htop-tycoon?style=for-the-badge" alt="Issues"></a>
  <a href="https://github.com/sigco3111/idea-bank/blob/main/TUI_Game_Project_Ideas.md"><img src="https://img.shields.io/badge/idea--bank-idea%231-blue?style=for-the-badge" alt="Idea Bank #1"></a>
</p>

---

## 🎮 컨셉

`htop`과 **100% 동일한 UI**(막대 그래프, 트리뷰, 색상, 키바인딩)로 회사 경영 게임을 합니다.
옆에서 보면 "아 IT 운영팀이 서버 모니터링하네" 하는데 정작 게임 중.

### 메타포

| 시스템 지표 | 회사 자원 |
|-------------|-----------|
| **CPU 사용률** | 매출 / 마케팅팀 생산성 |
| **메모리 점유** | 재고 / 자산 |
| **스왑** | 부채 / 외부 자금 |
| **좀비 프로세스 (Z)** | 퇴사 위기 직원 |
| **Load Average** | 시장 수요 / 주문량 |
| **nice 값** | 직원 직급 (-20=임원, +19=인턴) |
| **업타임** | 회사 운영 기간 |

---

## 🚀 빠른 시작

```bash
git clone https://github.com/sigco3111/htop-tycoon
cd htop-tycoon
pip install -e .
htop-tycoon
```

> Python 3.11+, `textual`, `rich` 필요. (`pip install textual rich`)

---

## ⌨️ 키 바인딩 (htop과 동일)

| 키 | htop 의미 | 게임 의미 |
|----|----------|-----------|
| `F1` / `h` | 도움말 | 게임 가이드 |
| `F2` / `S` | 설정 | 경영 정책 편집 |
| `F3` / `/` | 검색 | 직원/부서 검색 |
| `F4` / `\` | 필터 | 부서별 보기 |
| `F5` / `t` | 트리뷰 | 조직도 |
| `F6` / `<` `>` | 정렬 | KPI별 정렬 |
| `F7` / `]` | nice + | 승진 |
| `F8` / `[` | nice - | 감봉 / 강등 |
| `F9` / `k` | 프로세스 kill | **해고** ⚠️ |
| `F10` / `q` | 종료 | 게임 종료 |
| `Space` | 태그 | 직원 하이라이트 |
| `u` | 유저 필터 | 부서장 단독 보기 |
| `H` | 스레드 토글 | 부서별 업무량 |
| `p` | 경로 | 부서 위치 |
| `M` / `P` / `T` | 메모리/CPU/시간 정렬 | KPI별 재정렬 |

---

## 🏗️ 프로젝트 구조 (예정)

```
htop-tycoon/
├── pyproject.toml          # 패키지 설정
├── README.md               # 이 파일
├── LICENSE                 # MIT
├── src/
│   └── htop_tycoon/
│       ├── __init__.py
│       ├── app.py          # textual 앱 진입점
│       ├── game.py         # 경영 시뮬레이션 엔진
│       ├── widgets/        # 커스텀 TUI 위젯
│       │   ├── cpu_bar.py  # CPU 막대 (=매출)
│       │   ├── mem_bar.py  # 메모리 막대 (=재고)
│       │   └── proc_tree.py # 직원 트리뷰
│       └── data/
│           └── departments.py # 부서 정의
└── tests/
    └── test_game.py
```

---

## 🛣️ 로드맵

### v0.1.0 — MVP (현재)
- [ ] 기본 htop UI (CPU/메모리 막대, 프로세스 트리뷰)
- [ ] 단순 경영 시뮬 (직원 5명, 1개 부서, 4분기)
- [ ] `F9` 해고, `F7/F8` 승진/감봉

### v0.2.0 — 부서 확장
- [ ] 다중 부서 (마케팅/개발/영업/경영지원)
- [ ] 부서 간 자원 이동 (drag & drop)
- [ ] 분기별 재무제표 (`F2` 설정창)

### v0.3.0 — 멀티캠페인
- [ ] 시장 이벤트 시스템 (경기 변동)
- [ ] 경쟁사 등장
- [ ] 투자 라운드 (`IPO` 키 바인딩)

### v1.0.0 — 릴리즈
- [ ] 멀티플레이어 (여러 htop 창 = 여러 회사)
- [ ] 세이브/로드
- [ ] Steam/itch.io 배포
- [ ] ASCII 아트 로고

---

## 🤝 기여

환영! 다음 절차 권장:

1. Issue로 컨셉 합의
2. Fork → 브랜치 → PR
3. `pytest tests/` 통과 필수

자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md) (예정) 참고.

---

## 📄 라이선스

MIT — 자세한 내용은 [LICENSE](LICENSE) 참고.

---

## 🔗 관련 링크

- 💡 [idea-bank #1](https://github.com/sigco3111/idea-bank/blob/main/TUI_Game_Project_Ideas.md) — 이 프로젝트의 모태
- 🎮 [TUI 게임 카테고리](https://github.com/sigco3111/idea-bank/blob/main/TUI_Game_Project_Ideas.md) — 형제 프로젝트 19개
- 🏢 [sigco3111](https://github.com/sigco3111) — 만든 사람

---

> **"이거 htop이야 경영 시뮬이야?" — 회사에서 누가 물어봐도 둘 다 맞는 답.**
