# Indian Equity Research System

A point-in-time research platform for Indian cash equities.

> ### ⚠️ Research only — this software cannot trade
>
> This project has **no broker integration, no market-data connectivity and no
> ability to place, modify or cancel an order**. It does not connect to the
> Groww Trading API, to NSE, to BSE or to any external service. It produces
> **no investment recommendations**.
>
> Nothing in this repository is investment advice. Any strategy developed here
> is a research artefact until it has been validated out of sample and
> reviewed by a human.

---

## Purpose

To find out — honestly, and with the evidence bar set before the experiment —
whether a disciplined, cost-aware, systematic process can beat a Nifty 100
index fund **after every cost and every tax**.

The likeliest outcome is that it cannot. Establishing that with evidence is a
successful result and is the reason the project is structured as research
rather than as a trading system.

## Current phase

**Phase 1 — Research Foundation.** Project skeleton, typed configuration,
structured logging, database plumbing, a small read-only CLI, tests, and the
pre-registered hypotheses in [`HYPOTHESES.md`](HYPOTHESES.md).

### What exists

- Layered, validated configuration (YAML for non-secrets, environment
  variables for secrets) with production safety checks
- Structured logging with credential redaction
- SQLAlchemy 2.x declarative base with Alembic-ready naming conventions
- Engine, session factory and a read-only database health check
- CLI: `version`, `config-check`, `db-health`
- Generic date utilities (weekday and timezone helpers only)
- Unit and integration test suites
- Local PostgreSQL via Docker Compose
- Six pre-registered, falsifiable research hypotheses, all `NOT_TESTED`

### What does not exist (deliberate non-goals for this phase)

| Not implemented | Belongs to |
|---|---|
| NSE / BSE scraping, bhavcopy ingestion | Phase 2 |
| Corporate-action processing | Phase 2 |
| Historical index membership reconstruction | Phase 2 |
| Backtesting engine | Phase 3 |
| Momentum, quality or any other signal | Phase 4 |
| Portfolio construction, risk engine | Phase 6 |
| Shadow portfolio generation | Phase 7 |
| **Groww API authentication, market data or orders** | **Much later, if ever** |
| Live or paper order placement | **Not in scope for this project** |
| Machine learning, news processing, LLM features | Later, only if a baseline works |

**No database tables are defined yet.** Modelling instruments, prices and
corporate actions is deferred until the point-in-time requirements are fixed,
because retrofitting point-in-time correctness into an existing schema is far
more expensive than designing for it.

## Technology stack

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Layout | `src/` |
| Packaging / environments | `uv` |
| Configuration | `pydantic-settings` (env vars) + YAML (non-secrets) |
| Database | PostgreSQL 16 via SQLAlchemy 2.x, Alembic-ready |
| Driver | `psycopg` 3 |
| Local services | Docker Compose |
| Tests | `pytest` |
| Lint / format | `ruff` |
| Types | `mypy` (strict) |
| Logging | Standard library, structured format, secret redaction |

Rationale in [`docs/adr/0001-initial-technology-stack.md`](docs/adr/0001-initial-technology-stack.md).

## Local setup

Prerequisites: [`uv`](https://docs.astral.sh/uv/), `git`, and optionally
Docker (needed only for the integration tests).

```bash
# 0. Check prerequisites. Changes nothing.
python3 scripts/bootstrap.py

# 1. Create the virtual environment and install everything.
#    uv provisions Python 3.12 itself; no system Python 3.12 required.
uv sync --extra dev

# 2. Local configuration. .env is git-ignored.
cp .env.example .env

# 3. Optional: start PostgreSQL.
make db-up

# 4. Verify the environment end to end.
uv run python scripts/verify_environment.py
```

## CLI

```bash
uv run python -m indian_equity_research version        # prints the version
uv run python -m indian_equity_research config-check   # validates config, masks secrets
uv run python -m indian_equity_research db-health      # exits non-zero if unreachable
```

Exit codes: `0` success, `1` check failed, `2` usage error.

## Tests

```bash
make test-unit          # no database required
make db-up
make test-integration   # requires PostgreSQL
make test               # everything; integration tests skip if PostgreSQL is absent
make check              # format-check + lint + typecheck + unit tests (what CI runs)
```

Tests never access the network and never read a developer's `.env`.

## Developer commands

`make help` lists everything. The most used:

| Command | Purpose |
|---|---|
| `make install` | Create the venv and install dependencies |
| `make format` | Format and auto-fix with ruff |
| `make lint` | Lint with ruff |
| `make typecheck` | Strict type check with mypy |
| `make test` / `test-unit` / `test-integration` | Test suites |
| `make db-up` / `db-down` / `db-logs` | Local PostgreSQL |
| `make config-check` / `db-health` / `version` | CLI shortcuts |
| `make verify` | Full environment verification |
| `make clean` | Remove caches (never touches `data/` or `.env`) |

## Repository layout

```
configs/     Non-sensitive YAML configuration, layered by environment
data/        Local data lake (git-ignored except .gitkeep). Empty by design.
docs/        Architecture, data principles, architecture decision records
migrations/  Reserved for Alembic. No migrations yet; no tables exist.
notebooks/   Exploration only. Never imported by src/.
scripts/     Bootstrap and environment verification (no side effects)
src/         The package
tests/       Unit and integration suites
```

## Documentation

- [`HYPOTHESES.md`](HYPOTHESES.md) — pre-registered hypotheses H1–H6. **Read
  this before writing any research code.**
- [`docs/architecture.md`](docs/architecture.md) — target architecture, with
  every future component marked unimplemented
- [`docs/data_principles.md`](docs/data_principles.md) — the non-negotiable
  data rules
- [`docs/adr/`](docs/adr/) — architecture decision records

## Security

- Secrets live only in `.env` (git-ignored) and process environment variables.
- YAML configuration files must never contain a credential.
- Logs pass through a redaction filter; database URLs are rendered with the
  password masked.
- No broker, exchange or market-data credentials exist in this project, and
  none are required.

## Safety statement

This software performs **no trading of any kind**. It cannot place, modify or
cancel an order. It has no connection to any broker. It generates no buy or
sell recommendations.

Investing in equities carries the risk of permanent capital loss. Past
performance of any index, factor or strategy is not indicative of future
results. Nothing produced by this project is investment, legal or tax advice.
