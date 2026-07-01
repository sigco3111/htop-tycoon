.PHONY: install test lint typecheck run build release clean

install:
	uv sync --all-extras --dev

test:
	uv run pytest -q --cov=src/htop_tycoon --cov-report=term-missing

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src/

run:
	uv run python -m htop_tycoon

build:
	uv build

release:
	@git diff --quiet || (echo "ERROR: working tree dirty" && exit 1)
	@grep '^version = "3.0.0"' pyproject.toml > /dev/null || (echo "ERROR: pyproject version != 3.0.0" && exit 1)
	@echo "Run: git tag v3.0.0 && git push origin v3.0.0"

clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache dist build src/htop_tycoon.egg-info
