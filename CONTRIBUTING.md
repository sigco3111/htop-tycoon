# Contributing

Thanks for your interest in htop-tycoon. This document covers the development
setup, pull request process, and code style expectations. For the project
overview and key bindings, see [README.md](README.md). For the per-release
change log, see [CHANGELOG.md](CHANGELOG.md).

## Development setup

Requirements:

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/) (package manager and runner)
- A terminal that renders CJK correctly (any modern Linux or macOS terminal; Windows Terminal on Windows 11)

Install all runtime and dev dependencies in one step:

```bash
uv sync --all-extras --dev
```

Common Makefile targets:

```bash
make install     # uv sync --all-extras --dev
make test        # uv run pytest -q
make lint        # uv run ruff check src/ tests/
make typecheck   # uv run mypy src/
make run         # uv run python -m htop_tycoon
make build       # uv build (wheel + sdist into dist/)
make clean       # remove build artifacts and caches
make release     # precondition check + tag print (see Releasing below)
```

## Pull request process

1. Branch from `main` using a descriptive name, e.g. `feat/<scope>-<short-desc>` or `fix/<scope>-<short-desc>`.
2. Make atomic commits. One logical change per commit. Use Conventional Commits where practical (`feat(...)`, `fix(...)`, `test(...)`, `docs(...)`, `chore(...)`, `ci(...)`).
3. Before pushing, all three local quality gates must pass:
   ```bash
   uv run pytest -q
   uv run ruff check src/ tests/
   uv run mypy src/
   ```
4. Reference the relevant todo from `.omo/plans/htop-tycoon.md` in the commit body or PR description if the change implements or extends a planned task.
5. Open a pull request against `main`. CI must be green on Linux, macOS, and Windows (pytest only) before merge.
6. After merge, the maintainer tags the release and the GitHub Actions release workflow attaches the wheel and sdist to the GitHub Release.

## Code style

- **Formatter / Linter**: `ruff` (line-length = 100, target Python 3.11, rules `E`, `W`, `F`, `I`, `B`, `UP`).
- **Type checker**: `mypy --strict`. All public functions, methods, and modules require type hints.
- **Domain invariants** (enforced by the test suite):
  - All RNG flows must go through `GameRNG(seed)`. Do not use `import random` anywhere outside `src/htop_tycoon/rng.py`.
  - `GameState` is authoritative and effectively frozen. Engine functions are the only producers of new states; UI handlers must not mutate state directly.
  - Action functions return `(GameState, list[Event])`. Do not call `event_bus.publish(...)` inside core actions; events are pure data emitted by the engine.
  - `CORRUPTION_RECOVERY_SEED = 0` is the deterministic recovery seed. Do not derive recovery seeds from `time.time()`.
  - Time scale is fixed at 1 real-second = 1 game-week. Tune balance via `src/htop_tycoon/data/balance.yaml` and `seeds.yaml`, not by changing the time scale.
  - All numeric game constants live in `balance.yaml`. No hardcoded magic numbers (e.g. -500, +300) in source or data files.
- **No emoji** in source, docs, README, CHANGELOG, or commit messages.
- **Commit messages** must be short, task-focused, and free of emoji. Conventional Commits format is encouraged.
- **Scope ceiling**: no more than 5 endings, 5 departments, 3 products, 3 competitors. Plan revisions are required to exceed these limits.

## Releasing (maintainers only)

`make release` is a precondition check, not a tagging command. It enforces:

1. The working tree is clean (`git status --porcelain` is empty).
2. `pyproject.toml` matches the version passed in (default: the value in `pyproject.toml`).

If both pass, the target prints the exact commands to run:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The push triggers `.github/workflows/release.yml`, which builds the wheel and sdist, runs lint, type-check, and tests as gates, and attaches the artifacts to the GitHub Release. PyPI publishing is a manual step for v0.1.0.

## Reporting bugs

Open a GitHub issue with:

- Steps to reproduce (seed, tick-rate, tick number, key sequence)
- Expected vs. actual behavior
- Python version, OS, and terminal
- Output of `uv run pytest -q` if the bug appears to be in the engine or persistence layer

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See [LICENSE](LICENSE).
