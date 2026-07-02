.PHONY: help install sync test test-pilot test-integration lint typecheck format run build release clean coverage docs-screenshot v3-info

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: ## Install dev dependencies via uv
	uv sync --all-extras --dev

sync: ## Sync deps (no extras)
	uv sync

test: ## Run full test suite with coverage
	uv run pytest --cov=htop_tycoon --cov-report=term-missing

test-pilot: ## Run pilot (UI) tests only
	uv run pytest tests/pilot -v

test-integration: ## Run integration tests only
	uv run pytest tests/test_strategy_integration.py tests/test_tick_integration.py tests/persistence/ -v

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

release: ## v3.0 release preconditions (lint + typecheck + full test)
	@echo "Running v3.0 release preconditions..."
	@uv run ruff check
	@uv run mypy --strict src tests
	@uv run pytest -q
	@echo "All gates green. v3.0 ready."
	@echo "Note: this project does NOT auto-publish to PyPI."
	@echo "Run 'make build' to produce wheel + sdist artifacts."

clean: ## Remove build artifacts, caches
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

coverage: ## Run tests with detailed coverage report
	uv run coverage run -m pytest
	uv run coverage report -m
	uv run coverage html

docs-screenshot: ## Re-run pilot screenshot test (regenerates docs/screenshots/*.svg)
	uv run pytest tests/pilot -v

v3-info: ## Print v3.0 status summary
	@echo "htop-tycoon v3.0.0"
	@echo "===================="
	@uv run python -c "from htop_tycoon import __version__; print(f'Package version: {__version__}')"
	@echo "Test count: $$(uv run pytest --collect-only -q 2>/dev/null | tail -1)"
	@echo "Source files: $$(find src -name '*.py' | wc -l | tr -d ' ')"
	@echo "Test files: $$(find tests -name '*.py' | wc -l | tr -d ' ')"