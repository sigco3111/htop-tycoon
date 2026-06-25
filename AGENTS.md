# htop-tycoon — Agent Knowledge Base

## OVERVIEW

Terminal UI business simulator disguised as htop, Korean UI by default. Deep scope: 5 departments, 3 products, 3 competitors, 5 endings. Python 3.11+ using Textual, Rich, pyyaml. Save/load via JSON, planned GitHub release v0.1.0.

## STRUCTURE

Current files and planned layout (high level):

- src/htop_tycoon/
  - domain/              # game models, types
  - engine/              # core turn/tick logic, state transitions
  - ui/                  # Textual widgets, screens, localization
  - bindings/            # CLI, args, integration glue
  - persistence/         # save/load, json adapters
  - data/                # balance.yaml, seed fixtures
- tests/                 # unit and deterministic integration tests
- .github/workflows/     # CI, test matrix
- .omo/                  # planning, drafts, AGENTS.md (do not edit here)
- Makefile               # common targets
- pyproject.toml         # packaging, deps

TBD: packaging layout for console entry point, Windows console support glue, optional extras.

## WHERE TO LOOK

Tech stack / architecture  -> `.omo/plans/htop-tycoon.md`
Interview decisions         -> `.omo/drafts/htop-tycoon.md`
Conventions / anti-patterns-> `.omo/plans/htop-tycoon.md` (see "Must NOT have" and each todo's "Must NOT do")
User-facing                -> `README.md` (pre-existing Korean, do not modify)
Planning subdir            -> `.omo/AGENTS.md` (planning agent notes, do not edit here)

## CRITICAL INVARIANTS

- Determinism: All RNG flows go through `GameRNG(seed)`. No bare `random.*` in library code. Rationale: reproducible runs for tests and CI.
- State boundary: `GameState` is authoritative and effectively frozen. Engine produces state, persistence writes state, UI reads state; UI handlers MUST NOT mutate state directly. Rationale: prevents hidden side effects and race conditions.
- Event publishing: pure functions return `(GameState, list[Event])`. Do not call `event_bus.publish(...)` inside core actions. Rationale: testable side-effect isolation.
- Corruption recovery seed: `CORRUPTION_RECOVERY_SEED = 0` constant used for recovery paths. NEVER derive recovery seed from `time.time()`. Rationale: deterministic recovery and reproducible debugging.
- Time scale: map 1 real-second = 1 game-week, fixed in engine loop. Tune balance via `balance.yaml`, not by changing the time scale. Rationale: balance lives in data, not code.
- SECRET ending flag: condition is `all_depts_unlocked AND all_employees_skill == max_skill AND secret_investor_cleared`. Use `skill` metric (not satisfaction). Flip resolution flag on RESOLUTION step only. Rationale: explicit, auditable endings.

## ANTI-PATTERNS

- No bare `random.*` outside `rng.py` or the RNG adapter. Use `GameRNG(seed)`.
- Do not mutate `GameState` outside `engine/` functions. No direct field writes in UI handlers.
- No `event_bus.publish` calls inside action functions or metrics collectors.
- No `time.sleep` calls inside widgets or engine ticks.
- Do not derive seeds from `time.time()` except for the CLI default `--seed` help text.
- Limit scope: no more than 5 endings, 5 departments, 3 products, 3 competitors. Violations require plan revision.
- Forbidden integrations/features: psutil, SQLite as primary state store, multiplayer/online features, sound, mobile builds, web GUI, additional i18n frameworks, marketing campaign systems, R&D tech trees, loans/stock simulation, achievements, tutorial branches, difficulty modifiers, modding or replay frameworks.
- No hardcoded magic numbers like -500 or +300 anywhere in code or data; all numeric game constants must live in `balance.yaml`.
- Footer and UI: do not include English htop F-key labels in the footer; keep Korean UI by default.
- No emoji anywhere in source, docs, README headers, or in commit messages.

## UNIQUE STYLES

- Commits: atomic, one todo per commit, Conventional Commits where practical. Keep messages short and task-focused.
- Branch: use `feat/htop-tycoon-v0.1.0` for Wave 1 work.
- Tagging: create `v0.1.0` only after PR merge and `make release` preconditions pass.
- Language: bilingual project: Korean UI and Korean+English README, but code and tests are English identifiers and docstrings.
- Tests: deterministic tests only; CI must pass identical seeds across matrix.
- Tuning: `balance.yaml` is the single tunable source and must be frozen between waves; changes require plan update and a new wave note.

## COMMANDS

```
uv sync
make test
make run
make build
make release
python -m htop_tycoon --seed=42 --tick-rate=1
python -m htop_tycoon --seed=42 --ticks=1000 --no-autosave
```

## NOTES

- Repository is planning-only until Wave 1+ runs. No implementation work until the assigned todo is claimed.
- Before implementing any todo, READ the corresponding todo in `.omo/plans/htop-tycoon.md`. Todos are decision-complete; workers should have zero judgment calls.
- There are 41 todos total in the plan; they are decision-complete and cover conventions, anti-patterns, and acceptance criteria. If a constant, invariant, or convention must change, update the plan first and record the rationale.
- This AGENTS.md is the human-and-agent guide for contributors and automated agents. Keep it telegraphic and deterministic.
