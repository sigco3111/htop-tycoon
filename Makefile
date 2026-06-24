# htop-tycoon Makefile
# Common developer targets. `make release` has preconditions (T1 contract).

.PHONY: install test run build clean lint typecheck release help

# Use bash explicitly for shell control structures in release target.
SHELL := /usr/bin/env bash

help:
	@echo "htop-tycoon v0.1.0 - common targets:"
	@echo "  make install    - uv sync (install dev + runtime deps)"
	@echo "  make test       - uv run pytest -q"
	@echo "  make lint       - uv run ruff check src/ tests/"
	@echo "  make typecheck  - uv run mypy src/"
	@echo "  make run        - uv run python -m htop_tycoon"
	@echo "  make build      - uv build (wheel + sdist into dist/)"
	@echo "  make clean      - remove build artifacts, caches"
	@echo "  make release    - precondition check + tag v\$(VERSION) (T1 contract)"

install:
	uv sync --all-extras --dev

test:
	uv run pytest -q

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src/

run:
	uv run python -m htop_tycoon

build:
	uv build

clean:
	rm -rf dist/ build/ .pytest_cache/ .coverage htmlcov/ .ruff_cache/ .mypy_cache/ *.egg-info/ src/*.egg-info/

# Preconditions: clean tree + pyproject version matches tag.
# Fails with an actionable error if either is violated.
VERSION ?= $(shell grep '^version = ' pyproject.toml | head -1 | sed -E 's/version = "([^"]+)".*/\1/')
TAG := v$(VERSION)

release:
	@echo "Release preconditions for $(TAG):"
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: working tree is dirty. Commit or stash first." >&2; \
		git status --short >&2; \
		exit 1; \
	fi
	@if ! grep -q "^version = \"$(VERSION)\"$$" pyproject.toml; then \
		echo "ERROR: pyproject.toml version does not match '$(VERSION)'." >&2; \
		exit 1; \
	fi
	@echo "All preconditions pass. To release:" >&2
	@echo "  git tag $(TAG)" >&2
	@echo "  git push origin $(TAG)" >&2
	@echo "  (release workflow will attach wheel + sdist to GitHub Release)" >&2
