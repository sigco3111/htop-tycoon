.PHONY: help install sync test test-pilot lint typecheck format run build release clean docs-screenshot

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: ## Install dev dependencies via uv
	uv sync --all-extras --dev

sync: ## Sync deps (no extras)
	uv sync

test: ## Run full test suite with coverage
	uv run pytest --cov=htop_tycoon --cov-report=term-missing

test-pilot: ## Run pilot (UI) tests only
	uv run pytest tests/pilot -v

test-fast: ## Run tests without coverage (faster)
	uv run pytest -q

lint: ## Run ruff lint
	uv run ruff check

lint-fix: ## Run ruff lint with autofix
	uv run ruff check --fix

typecheck: ## Run mypy --strict
	uv run mypy --strict src tests

format: ## Run ruff format
	uv run ruff format

run: ## Run the TUI app
	uv run python -m htop_tycoon

build: ## Build wheel + sdist
	uv build

release: ## Verify release preconditions (tag-only, no push)
	@echo "Release preconditions checked by CI in v3.0+. See docs/RELEASING.md."

clean: ## Remove build artifacts, caches
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

docs-screenshot: ## Re-run pilot screenshot test (regenerates docs/screenshots/*.svg)
	uv run pytest tests/pilot/test_boot.py -v