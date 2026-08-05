# ===========================================================================
# Indian Equity Research System - developer commands
#
# Every target is local and offline. Nothing here downloads market data,
# contacts an exchange or connects to a broker.
# ===========================================================================

.DEFAULT_GOAL := help
.PHONY: help install format format-check lint typecheck test test-unit test-integration \
        check db-up db-down db-logs db-wait config-check db-health version verify bootstrap clean

UV ?= uv
RUN := $(UV) run

# Compose invocation differs by install method:
#   - Docker Desktop / recent Docker Engine -> `docker compose` (plugin)
#   - older or Homebrew-formula installs     -> `docker-compose` (standalone)
# Detect rather than assume, so a wrong guess does not surface as the very
# confusing "unknown shorthand flag: 'd' in -d".
COMPOSE ?= $(shell \
	if docker compose version >/dev/null 2>&1; then echo "docker compose"; \
	elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; \
	else echo "NOCOMPOSE"; fi)

define require_compose
	@if [ "$(COMPOSE)" = "NOCOMPOSE" ]; then \
		echo "Docker Compose was not found."; \
		echo ""; \
		echo "  1. Install Docker Desktop:  brew install --cask docker"; \
		echo "  2. LAUNCH IT ONCE:          open -a Docker"; \
		echo "     (first launch installs the compose CLI plugin)"; \
		echo "  3. Verify:                  docker compose version"; \
		echo ""; \
		echo "Integration tests are optional locally - they run in CI."; \
		echo "Everything else works without Docker: make check"; \
		exit 1; \
	fi
	@if ! docker info >/dev/null 2>&1; then \
		echo "Docker is installed but the daemon is not running."; \
		echo "Start it with:  open -a Docker   (wait for the whale icon)"; \
		exit 1; \
	fi
endef

help:  ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------
bootstrap:  ## Check local prerequisites and print setup steps (changes nothing).
	@python3 scripts/bootstrap.py

install:  ## Create the virtual environment and install all dependencies.
	$(UV) sync --extra dev
	@mkdir -p data/raw data/interim data/processed data/reference
	@echo "Installed. Copy .env.example to .env and edit it if you need a database."

verify:  ## Verify the installed environment end to end.
	$(RUN) python scripts/verify_environment.py

# --------------------------------------------------------------------------
# Code quality
# --------------------------------------------------------------------------
format:  ## Format the codebase with ruff.
	$(RUN) ruff format .
	$(RUN) ruff check . --fix

format-check:  ## Verify formatting without modifying files (use in CI).
	$(RUN) ruff format --check .

lint:  ## Lint with ruff.
	$(RUN) ruff check .

typecheck:  ## Static type checking with mypy.
	$(RUN) mypy

# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
test:  ## Run every test (integration tests skip if PostgreSQL is absent).
	$(RUN) pytest

test-unit:  ## Run unit tests only.
	$(RUN) pytest -m "not integration" tests/unit

test-integration:  ## Run integration tests only (needs `make db-up`).
	$(RUN) pytest -m integration tests/integration

check: format-check lint typecheck test-unit  ## Everything CI runs.

# --------------------------------------------------------------------------
# Local database
# --------------------------------------------------------------------------
db-up:  ## Start PostgreSQL in the background.
	$(call require_compose)
	$(COMPOSE) up -d postgres

db-wait:  ## Block until PostgreSQL reports healthy.
	$(call require_compose)
	@echo "Waiting for PostgreSQL..."
	@for i in $$(seq 1 30); do \
		if $(COMPOSE) exec -T postgres pg_isready -q; then echo "ready"; exit 0; fi; \
		sleep 2; \
	done; echo "PostgreSQL did not become ready in time"; exit 1

db-down:  ## Stop PostgreSQL (the data volume is preserved).
	$(call require_compose)
	$(COMPOSE) down

db-logs:  ## Tail the PostgreSQL logs.
	$(call require_compose)
	$(COMPOSE) logs -f postgres

# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
version:  ## Print the package version.
	$(RUN) python -m indian_equity_research version

config-check:  ## Validate configuration (secrets stay masked).
	$(RUN) python -m indian_equity_research config-check

db-health:  ## Check database connectivity (non-zero exit when unavailable).
	$(RUN) python -m indian_equity_research db-health

# --------------------------------------------------------------------------
# Housekeeping
# --------------------------------------------------------------------------
clean:  ## Remove caches and build artefacts. Data and .env are untouched.
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml build dist
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
